"""Operations Agent: deterministic live business operations over SQLite.

CrewAI is used to classify the operational intent, but every live value comes
from the active business database. Financial aggregation is always Python/SQL.
"""
import re
from database import (
    list_products,
    find_supplier_for_product,
    create_supplier_order,
    log_activity,
    query_today_sales,
    query_sales_last_days,
)
from agent_runtime import crew_json
from crewai_tools import get_inventory_tools

OPERATION_INTENTS = {
    "inventory", "low_stock", "inventory_all", "price", "sales_today",
    "orders_today", "sales_7d", "supplier_lookup", "supplier_status", "supplier_order", "unknown",
}


def inventory_snapshot(business_id=1):
    return [
        {
            "id": p["id"], "name": p["name"], "stock": p["stock_quantity"],
            "minimum_stock": p["minimum_stock"], "unit": p["unit"],
            "low_stock": float(p["stock_quantity"]) <= float(p["minimum_stock"]),
        }
        for p in list_products(business_id)
    ]


def low_stock_items(business_id=1):
    return [x for x in inventory_snapshot(business_id) if x["low_stock"]]


def _find_product(text, business_id=1):
    q = (text or "").strip().lower()
    products = list_products(business_id)
    best = None
    best_score = 0
    for p in products:
        names = [p.get("name", "")] + [x.strip() for x in str(p.get("aliases", "")).split(",") if x.strip()]
        for name in names:
            n = name.lower()
            if n and n in q:
                score = 100 + len(n)
                if score > best_score:
                    best, best_score = p, score
    return best


def _requested_quantity(text):
    q = (text or "").lower()
    patterns = [
        r"(?:order|mangwa|lao|quantity|qty)\s*(?:of|ka|ki|ke)?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|pack|packs|unit|units|piece|pieces)",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            value = float(m.group(1))
            if value > 0:
                return value
    return None


def supplier_draft(product_id, business_id=1, quantity=None, created_by=0):
    product = next((p for p in list_products(business_id) if int(p["id"]) == int(product_id)), None)
    if not product:
        raise ValueError("Product not found.")
    supplier = find_supplier_for_product(product_id, business_id)
    if not supplier:
        raise ValueError("No supplier is configured for this product.")
    suggested = quantity if quantity is not None else max(
        float(product["minimum_stock"]) * 2 - float(product["stock_quantity"]), 1
    )
    return {"supplier": supplier, "product": product, "suggested_quantity": suggested}


def _fallback_intent(text):
    q = (text or "").strip().lower()
    if any(x in q for x in ["order bana", "order banado", "order bna", "reorder", "purchase", "mangwa"]):
        return {"intent": "supplier_order", "reason": "supplier/reorder request"}
    if any(x in q for x in ["supplier status", "supplier order status", "order status", "pending supplier", "supplier ki status"]):
        return {"intent": "supplier_status", "reason": "supplier/order status request"}
    if any(x in q for x in ["supplier kaun", "supplier", "vendor", "kis supplier", "supplier se"]):
        return {"intent": "supplier_lookup", "reason": "supplier lookup request"}
    if any(x in q for x in ["pichlay 7", "pichle 7", "last 7", "7 days", "haftay", "week"]):
        if any(x in q for x in ["sales", "sale", "revenue", "bikri"]):
            return {"intent": "sales_7d", "reason": "seven-day sales query"}
    if any(x in q for x in ["aaj", "today", "aj", "آج"]):
        if any(x in q for x in ["sales", "sale", "revenue", "bikri", "total"]):
            return {"intent": "sales_today", "reason": "today sales query"}
        if any(x in q for x in ["orders", "order", "kitne"]):
            return {"intent": "orders_today", "reason": "today order-count query"}
    if any(x in q for x in ["price", "rate", "qeemat", "قیمت", "kitne ka", "kitnay ka"]):
        return {"intent": "price", "reason": "product price query"}
    if any(x in q for x in ["low stock", "low-stock", "kam stock", "stock kam", "khatam"]):
        return {"intent": "low_stock", "reason": "low-stock list query"}
    if any(x in q for x in ["sab products", "all products", "current stock", "inventory list", "sab ka stock"]):
        return {"intent": "inventory_all", "reason": "full inventory query"}
    if any(x in q for x in ["stock", "inventory", "available", "maujood", "اسٹاک", "انوینٹری"]):
        return {"intent": "inventory", "reason": "stock/inventory query"}
    return {"intent": "unknown", "reason": "unrecognized operational request"}


def classify_operation_request(text: str, business_id=1) -> dict:
    fallback = _fallback_intent(text)
    prompt = f"""Classify this Business Brain operational request into exactly one intent:
{', '.join(sorted(OPERATION_INTENTS))}
Return JSON only: {{"intent":"...","reason":"..."}}
Rules:
- supplier lookup (who supplies a product) -> supplier_lookup
- supplier/order status -> supplier_status
- supplier/reorder/order draft -> supplier_order
- product selling price -> price
- today's sales amount -> sales_today
- today's order count -> orders_today
- last 7 days sales amount -> sales_7d
- low-stock list -> low_stock
- all/current inventory list -> inventory_all
- one product stock -> inventory
Request: {text}
Business ID: {business_id}"""
    result = crew_json(
        "Operations Agent",
        "Interpret live inventory, sales and supplier requests and select the deterministic database workflow.",
        "You are a read/write-safe operations specialist. Never invent stock, prices, supplier facts, totals, or approval status.",
        prompt,
        fallback=fallback,
        tools=get_inventory_tools(),
    )
    if not isinstance(result, dict):
        return fallback
    intent = str(result.get("intent", "unknown")).strip().lower()
    return result if intent in OPERATION_INTENTS else fallback


def _fmt_num(value):
    return f"{float(value):g}"


def answer_inventory_question(text, business_id=1):
    product = _find_product(text, business_id)
    if product:
        stock = float(product.get("stock_quantity", 0) or 0)
        minimum = float(product.get("minimum_stock", 0) or 0)
        unit = product.get("unit", "unit")
        answer = f"**{product['name']}** ka current stock **{_fmt_num(stock)} {unit}** hai. Minimum stock **{_fmt_num(minimum)} {unit}** hai."
        if stock <= minimum:
            answer += " ⚠️ Ye low-stock level par hai."
        return {"ok": True, "answer": answer, "sources": [], "live_data": True}
    return answer_all_inventory(business_id) if _fallback_intent(text)["intent"] == "inventory_all" else {"ok": False, "error": "Mujhe is product ka naam catalog mein match nahi mila."}


def answer_all_inventory(business_id=1):
    rows = inventory_snapshot(business_id)
    if not rows:
        return {"ok": True, "answer": "Is business ke catalog mein koi active product nahi mila.", "sources": [], "live_data": True}
    lines = [f"- **{x['name']}** — {_fmt_num(x['stock'])} {x['unit']}" for x in rows]
    return {"ok": True, "answer": "**Current inventory:**\n" + "\n".join(lines), "sources": [], "live_data": True}


def answer_low_stock(business_id=1):
    rows = low_stock_items(business_id)
    if not rows:
        return {"ok": True, "answer": "Abhi koi product low-stock level par nahi hai.", "sources": [], "live_data": True}
    lines = [f"- **{x['name']}** — {_fmt_num(x['stock'])} {x['unit']} remaining (minimum {_fmt_num(x['minimum_stock'])})" for x in rows]
    return {"ok": True, "answer": "**Low-stock products:**\n" + "\n".join(lines), "sources": [], "live_data": True}


def answer_product_price(text, business_id=1):
    product = _find_product(text, business_id)
    if not product:
        return {"ok": False, "error": "Mujhe is product ka naam catalog mein match nahi mila."}
    price = product.get("price")
    if price is None:
        return {"ok": True, "answer": f"**{product['name']}** ki selling price abhi set nahi hai.", "sources": [], "live_data": True}
    return {"ok": True, "answer": f"**{product['name']}** ki current selling price **Rs {_fmt_num(price)} per {product.get('unit', 'unit')}** hai.", "sources": [], "live_data": True}


def answer_sales_today(business_id=1):
    data = query_today_sales(business_id)
    return {"ok": True, "answer": f"Aaj **{data['order_count']} confirmed orders** huay aur total sales **Rs {_fmt_num(data['sales_total'])}** hain.", "sources": [], "live_data": True}


def answer_orders_today(business_id=1):
    data = query_today_sales(business_id)
    return {"ok": True, "answer": f"Aaj **{data['order_count']} confirmed orders** hain.", "sources": [], "live_data": True}


def answer_sales_last_7_days(business_id=1):
    data = query_sales_last_days(business_id, 7)
    return {"ok": True, "answer": f"Pichlay **7 din** mein **{data['order_count']} confirmed orders** huay aur total sales **Rs {_fmt_num(data['sales_total'])}** hain.", "sources": [], "live_data": True}


def answer_supplier_status(business_id=1):
    from database import list_supplier_orders
    orders = list_supplier_orders(business_id, 20)
    if not orders:
        return {"ok": True, "answer": "Abhi koi supplier order nahi mila.", "sources": [], "live_data": True}
    lines = [f"- **Order #{o['id']} · {o['supplier_name']}** — {o['status']}" for o in orders]
    return {"ok": True, "answer": "**Supplier / order status:**\n" + "\n".join(lines), "sources": [], "live_data": True}

def answer_supplier_lookup(text, business_id=1):
    product = _find_product(text, business_id)
    if not product:
        return {"ok": False, "error": "Mujhe is product ka naam catalog mein match nahi mila."}
    supplier = find_supplier_for_product(product["id"], business_id)
    if not supplier:
        return {"ok": True, "answer": f"**{product['name']}** ke liye abhi koi supplier configured nahi hai.", "sources": [], "live_data": True}
    return {"ok": True, "answer": f"**{product['name']}** ka configured supplier **{supplier['name']}** hai.", "sources": [], "live_data": True}


def draft_supplier_order(text, business_id=1, created_by=0):
    product = _find_product(text, business_id)
    if not product:
        return {"ok": False, "error": "Supplier order ke liye product catalog mein nahi mila."}
    details = supplier_draft(product["id"], business_id, _requested_quantity(text), created_by)
    qty = float(details["suggested_quantity"])
    supplier = details["supplier"]
    order_id = create_supplier_order(
        supplier["id"],
        [{"product_id": product["id"], "quantity": qty, "unit_price": supplier.get("supplier_price")}],
        created_by,
        business_id,
    )
    log_activity(
        "Supplier order draft created",
        f"Draft #{order_id}: {product['name']} x {qty:g} for {supplier['name']}",
        "Business Brain",
        business_id,
    )
    return {
        "ok": True,
        "order_id": order_id,
        "answer": f"Supplier order draft **#{order_id}** ban gaya hai: **{product['name']} × {qty:g} {product.get('unit','unit')}** from **{supplier['name']}**. Human approval required before this supplier order is approved.",
        "sources": [],
        "requires_approval": True,
        "status": "Draft",
        "live_data": True,
    }


def execute_operation(text, business_id=1, created_by=0):
    """Run the selected Operations workflow; never use RAG for live facts."""
    classified = classify_operation_request(text, business_id)
    intent = classified.get("intent", "unknown")
    if intent == "inventory":
        return answer_inventory_question(text, business_id)
    if intent == "inventory_all":
        return answer_all_inventory(business_id)
    if intent == "low_stock":
        return answer_low_stock(business_id)
    if intent == "price":
        return answer_product_price(text, business_id)
    if intent == "sales_today":
        return answer_sales_today(business_id)
    if intent == "orders_today":
        return answer_orders_today(business_id)
    if intent == "sales_7d":
        return answer_sales_last_7_days(business_id)
    if intent == "supplier_lookup":
        return answer_supplier_lookup(text, business_id)
    if intent == "supplier_status":
        return answer_supplier_status(business_id)
    if intent == "supplier_order":
        return draft_supplier_order(text, business_id, created_by)
    return {"ok": False, "error": "Main is operational request ko confidently classify nahi kar saka."}
