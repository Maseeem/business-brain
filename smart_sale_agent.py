import json
import re
from product_tools import find_product_tool
from cart_tools import create_cart, add_item, calculate_subtotal, calculate_total
from database import list_products
from agent_runtime import crew_json

NUMBER_WORDS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "ek":1,"aik":1,"do":2,"du":2,"teen":3,"tin":3,"char":4,"chaar":4,"paanch":5,"panch":5,"che":6,"chay":6,"saat":7,"aath":8,"nau":9,"das":10,
    "ایک":1,"اک":1,"دو":2,"تین":3,"تِن":3,"چار":4,"پانچ":5,"چھ":6,"سات":7,"آٹھ":8,"آٹھ":8,"نو":9,"دس":10,"دونوں":2,
}

def _normalize_digits(text):
    return str(text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def _words_to_number(text):
    t=_normalize_digits(text).strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?",t): return float(t)
    return float(NUMBER_WORDS[t]) if t in NUMBER_WORDS else None

def _norm(s):
    s=_normalize_digits(s).lower()
    return re.sub(r"[^\w\s-]", " ", s, flags=re.UNICODE).strip()

def _quantity_markers(text):
    number_pattern = r"\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|ek|aik|do|du|teen|tin|char|chaar|paanch|panch|che|chay|saat|aath|nau|das|ایک|اک|دو|تین|تِن|چار|پانچ|چھ|سات|آٹھ|آٹھ|نو|دس|دونوں"
    return list(re.finditer(rf"(?<!\w)({number_pattern})(?=\s*(?:kg|kilo|kilos|kilogram|kilograms|کلو|کلوگرام|liter|litre|ltr|لٹر|لیٹر|pcs|piece|pieces|pack|packs|پیک|پیکٹ)?\s+|\s*$)", _norm(text), flags=re.I))


def _match_catalog_phrase(phrase, catalog):
    phrase_norm = _norm(phrase)
    best = None
    best_len = 0
    for product in catalog:
        aliases = [product["name"]] + [a.strip() for a in str(product.get("aliases", "")).split(",") if a.strip()]
        for alias in aliases:
            a = _norm(alias)
            if a and re.search(rf"(?<!\w){re.escape(a)}(?!\w)", phrase_norm) and len(a) > best_len:
                best, best_len = product, len(a)
    return best


def _fallback_extract(text, catalog):
    """Deterministically extract every quantity/name chunk, including unknown products."""
    normalized = _norm(text)
    markers = _quantity_markers(text)
    items = []
    if markers:
        for idx, marker in enumerate(markers):
            qty = _words_to_number(marker.group(1))
            if qty is None or qty <= 0:
                continue
            start = marker.end()
            end = markers[idx + 1].start() if idx + 1 < len(markers) else len(normalized)
            segment = normalized[start:end]
            segment = re.sub(r"^(?:kg|kilo|kilos|kilogram|kilograms|کلو|کلوگرام|liter|litre|ltr|لٹر|لیٹر|pcs|piece|pieces|pack|packs|پیک|پیکٹ)\s*", "", segment, flags=re.I)
            segment = re.sub(r"\s*(?:aur|and|or|,|،|;|\+|&)+\s*$", "", segment, flags=re.I).strip()
            if not segment:
                continue
            product = _match_catalog_phrase(segment, catalog)
            if product:
                items.append({"product_id": product["id"], "quantity": qty})
            else:
                # Keep the exact user-understood unknown item visible to callers.
                unknown_name = re.sub(r"\s+", " ", segment).strip(" ,،;|+")
                if unknown_name:
                    items.append({"unknown_name": unknown_name, "quantity": qty})
        if items:
            return {"items": items}

    # Fallback for product-first forms such as "Pepsi 2".
    found = []
    ordered = sorted(catalog, key=lambda p: max([len(_norm(p["name"]))] + [len(_norm(a)) for a in str(p.get("aliases", "")).split(",") if a.strip()]), reverse=True)
    for product in ordered:
        aliases = [product["name"]] + [a.strip() for a in str(product.get("aliases", "")).split(",") if a.strip()]
        for alias in sorted(aliases, key=len, reverse=True):
            a = _norm(alias)
            if not a or not re.search(rf"(?<!\w){re.escape(a)}(?!\w)", normalized):
                continue
            qty = 1.0
            m = re.search(rf"{re.escape(a)}\s*(?:x|×)?\s*(\d+(?:\.\d+)?)", normalized, flags=re.I)
            if m:
                qty = float(m.group(1))
            found.append({"product_id": product["id"], "quantity": qty})
            break
    return {"items": found}


def extract_order(text: str, business_id: int = 1) -> dict:
    catalog = [{"id": p["id"], "name": p["name"], "aliases": p.get("aliases", "") or "", "unit": p.get("unit", "unit")} for p in list_products(business_id)]
    extracted = _fallback_extract(text, catalog)
    raw_items = list(extracted["items"])

    # Product-first edits such as "Tissue 3 kar do" are handled separately.
    # This is additive: the generic quantity-first parser remains responsible for
    # preserving unknown items in mixed orders.
    known_ids = {x.get("product_id") for x in raw_items if x.get("product_id") is not None}
    normalized = _norm(text)
    for product in catalog:
        aliases = [product["name"]] + [a.strip() for a in str(product.get("aliases", "")).split(",") if a.strip()]
        for alias in sorted(aliases, key=len, reverse=True):
            a = _norm(alias)
            if not a or not re.search(rf"(?<!\w){re.escape(a)}(?!\w)", normalized):
                continue
            m = re.search(rf"{re.escape(a)}\s*(?:x|×)?\s*(\d+(?:\.\d+)?)", normalized, flags=re.I)
            if m and product["id"] not in known_ids:
                raw_items.append({"product_id": product["id"], "quantity": float(m.group(1))})
                known_ids.add(product["id"])
            break

    items = []
    unknown = []
    for item in raw_items:
        if "product_id" in item:
            product = next(p for p in catalog if p["id"] == item["product_id"])
            items.append({"product": product, "quantity": item["quantity"]})
        else:
            unknown.append({"name": item["unknown_name"], "quantity": item["quantity"]})
    return {"items": items, "unknown_items": unknown}

def build_cart(text: str, business_id: int = 1) -> dict:
    parsed = extract_order(text, business_id)
    cart = create_cart()
    missing_price = []
    for item in parsed["items"]:
        product = find_product_tool(item["product"]["name"], business_id)
        if not product:
            continue
        price = product.get("price")
        qty = float(item["quantity"])
        stock = float(product.get("stock_quantity", 0) or 0)
        cart.append({
            "product_id": product["id"], "name": product["name"], "quantity": qty,
            "unit_price": (float(price) if price is not None else None),
            "subtotal": (calculate_subtotal(qty, float(price)) if price is not None else None),
            "unit": product.get("unit", "unit"), "stock_quantity": stock,
        })
        if price is None:
            missing_price.append(product["name"])
    priced = [x for x in cart if x.get("subtotal") is not None]
    total = round(sum(x["subtotal"] for x in priced), 2) if priced else 0.0
    return {
        "cart": cart,
        "total": total,
        "missing_price": missing_price,
        "parsed_items": parsed["items"],
        "unknown_items": parsed.get("unknown_items", []),
        "unknown_products": parsed.get("unknown_items", []),
    }


def execute_sale_request(text: str, business_id: int = 1) -> dict:
    """Run the real Smart Sale Agent layer, then deterministic sale tools.

    CrewAI decides only that this is a cart-building workflow. It never receives
    authority to set prices, stock, subtotals, totals, or inventory changes.
    """
    fallback = {"action": "build_cart"}
    prompt = f"""You are the Business Brain Smart Sale Agent.
Interpret the request only as an order-understanding/orchestration task.
Return JSON only: {{"action":"build_cart"}}
Never calculate price, stock, subtotal, total, or inventory changes.
Those values come from SQLite and deterministic Python tools.
Business ID: {business_id}
Order: {text}"""
    plan = crew_json(
        "Smart Sale Agent",
        "Interpret customer sale requests and hand them to deterministic cart tools.",
        "You are a sales workflow specialist. Business calculations are never performed by the language model.",
        prompt,
        fallback=fallback,
    )
    if not isinstance(plan, dict) or plan.get("action") != "build_cart":
        plan = fallback
    result = build_cart(text, business_id)
    result["agent"] = "smart_sale"
    result["agent_plan"] = plan
    return result

def apply_cart_edit(cart, action: str, business_id: int = 1) -> dict:
    parsed=extract_order(action,business_id)
    if not parsed["items"]: return {"cart":cart,"total":0.0,"changed":False}
    new=list(cart)
    changed=False
    for item in parsed["items"]:
        pid=item["product"]["id"]; qty=float(item["quantity"])
        existing=next((x for x in new if x["product_id"]==pid),None)
        product=find_product_tool(item["product"]["name"],business_id)
        if existing:
            existing["quantity"]=qty
            existing["subtotal"]=(qty*existing["unit_price"] if existing.get("unit_price") is not None else None)
            existing["stock_quantity"]=float(product.get("stock_quantity",0) or 0) if product else existing.get("stock_quantity",0)
            changed=True
        elif product:
            price=product.get("price")
            new.append({"product_id":product["id"],"name":product["name"],"quantity":qty,"unit_price":(float(price) if price is not None else None),"subtotal":(qty*float(price) if price is not None else None),"unit":product.get("unit","unit"),"stock_quantity":float(product.get("stock_quantity",0) or 0)})
            changed=True
    total=round(sum(x["subtotal"] for x in new if x.get("subtotal") is not None),2)
    return {"cart":new,"total":total,"changed":changed}
