"""Deterministic live-data Q&A for Business Brain.

Live operational facts come from SQLite; document/process questions are left to RAG.
"""
import re
from datetime import datetime, timedelta
from database import _conn, list_products, find_supplier_for_product


def _fmt_num(value):
    try:
        n = float(value)
        return f"{n:g}"
    except Exception:
        return str(value)


def _find_product(question, business_id):
    q = (question or "").lower()
    products = list_products(business_id)
    best, best_score = None, 0
    tokens = [x for x in re.sub(r"[^a-z0-9\s\u0600-\u06ff]", " ", q).split() if len(x) > 1]
    for p in products:
        names = [p.get("name", "")] + [x.strip() for x in str(p.get("aliases", "")).split(",") if x.strip()]
        score = 0
        for name in names:
            n = name.lower()
            if n and n in q:
                score = max(score, 100 + len(n))
            else:
                score = max(score, sum(1 for t in tokens if t in n))
        if score > best_score:
            best, best_score = p, score
    return best


def _has_any(q, terms):
    return any(t in q for t in terms)


def answer_live_business_question(question, business_id=1):
    """Return a live DB answer when the question is about operational business facts.
    Returns None when the question should be handled by RAG/knowledge retrieval.
    """
    q = (question or "").strip().lower()
    if not q:
        return None

    # Product stock / availability.
    if _has_any(q, ["stock", "inventory", "available", "maujood", "اسٹاک", "انوینٹری"]):
        product = _find_product(q, business_id)
        if product:
            stock = product.get("stock_quantity", 0)
            minimum = product.get("minimum_stock", 0)
            unit = product.get("unit", "unit")
            answer = f"**{product['name']}** ka current stock **{_fmt_num(stock)} {unit}** hai. Minimum stock **{_fmt_num(minimum)} {unit}** hai."
            if float(stock) <= float(minimum):
                answer += " ⚠️ Ye low-stock level par hai."
            return {"ok": True, "answer": answer, "sources": [], "live_data": True}
        if _has_any(q, ["low stock", "kam stock", "low-stock"]):
            return _low_stock_answer(business_id)
        # A generic inventory question should still be useful.
        if _has_any(q, ["all", "sab", "list", "products", "items", "kon", "kaun"]):
            return _inventory_list_answer(business_id)

    # Explicit low-stock questions.
    if _has_any(q, ["low stock", "low-stock", "kam stock", "stock kam", "khatam"]):
        return _low_stock_answer(business_id)

    # Today's sales / orders.
    if _has_any(q, ["today", "aaj", "aaj ki", "today's", "aj", "آج"]):
        if _has_any(q, ["sales", "sale", "revenue", "total sale", "bikri"]):
            return _today_sales_answer(business_id)
        if _has_any(q, ["orders", "order", "kitne order", "orders kitne"]):
            return _today_orders_answer(business_id)

    # General sales/order questions with "total".
    if _has_any(q, ["sales", "sale", "revenue", "bikri"]) and _has_any(q, ["total", "kitni", "kitna", "how much", "amount"]):
        return _today_sales_answer(business_id)

    if _has_any(q, ["orders", "order"]) and _has_any(q, ["kitne", "how many", "count", "number", "total"]):
        return _today_orders_answer(business_id)

    # Product price.
    if _has_any(q, ["price", "rate", "cost", "qeemat", "قیمت", "kitne ka", "kitnay ka"]):
        product = _find_product(q, business_id)
        if product:
            price = product.get("price")
            if price is None:
                return {"ok": True, "answer": f"**{product['name']}** ki selling price abhi set nahi hai.", "sources": [], "live_data": True}
            return {"ok": True, "answer": f"**{product['name']}** ki current selling price **Rs {_fmt_num(price)} per {product.get('unit', 'unit')}** hai.", "sources": [], "live_data": True}

    # Supplier for a named product.
    if _has_any(q, ["supplier", "vendor", "supplier kaun", "kis supplier"]):
        product = _find_product(q, business_id)
        if product:
            supplier = find_supplier_for_product(product["id"], business_id)
            if supplier:
                return {"ok": True, "answer": f"**{product['name']}** ka configured supplier **{supplier['name']}** hai.", "sources": [], "live_data": True}
            return {"ok": True, "answer": f"**{product['name']}** ke liye abhi koi supplier configured nahi hai.", "sources": [], "live_data": True}

    # Recent sales summary / last 7 days.
    if _has_any(q, ["last 7 days", "7 days", "pichlay 7", "pichle 7", "haftay", "week"]):
        if _has_any(q, ["sales", "sale", "revenue", "bikri"]):
            return _period_sales_answer(business_id, 7)

    return None


def _low_stock_answer(business_id):
    products = [p for p in list_products(business_id) if float(p.get("stock_quantity", 0)) <= float(p.get("minimum_stock", 0))]
    if not products:
        return {"ok": True, "answer": "Abhi koi product low-stock level par nahi hai. ✅", "sources": [], "live_data": True}
    lines = [f"- **{p['name']}** — {_fmt_num(p['stock_quantity'])} {p.get('unit','unit')} (minimum {_fmt_num(p['minimum_stock'])})" for p in products]
    return {"ok": True, "answer": "**Low-stock products:**\n" + "\n".join(lines), "sources": [], "live_data": True}


def _inventory_list_answer(business_id):
    products = list_products(business_id)
    if not products:
        return {"ok": True, "answer": "Business Brain mein abhi koi active product nahi mila.", "sources": [], "live_data": True}
    lines = [f"- **{p['name']}** — {_fmt_num(p['stock_quantity'])} {p.get('unit','unit')}" for p in products]
    return {"ok": True, "answer": "**Current inventory:**\n" + "\n".join(lines), "sources": [], "live_data": True}


def _today_sales_answer(business_id):
    today = datetime.now().date().isoformat()
    c = _conn()
    row = c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total FROM sales WHERE business_id=? AND date(created_at)=?", (business_id, today)).fetchone()
    c.close()
    return {"ok": True, "answer": f"Aaj **{row['n']} sales/orders** record huay hain, total sales **Rs {_fmt_num(row['total'])}** hain.", "sources": [], "live_data": True}


def _today_orders_answer(business_id):
    today = datetime.now().date().isoformat()
    c = _conn()
    row = c.execute("SELECT COUNT(*) AS n FROM sales WHERE business_id=? AND date(created_at)=?", (business_id, today)).fetchone()
    c.close()
    return {"ok": True, "answer": f"Aaj **{row['n']} confirmed orders** hain.", "sources": [], "live_data": True}


def _period_sales_answer(business_id, days):
    start = (datetime.now().date() - timedelta(days=days-1)).isoformat()
    c = _conn()
    row = c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total FROM sales WHERE business_id=? AND date(created_at)>=?", (business_id, start)).fetchone()
    c.close()
    return {"ok": True, "answer": f"Pichlay **{days} din** mein **{row['n']} sales/orders** huay aur total sales **Rs {_fmt_num(row['total'])}** hain.", "sources": [], "live_data": True}
