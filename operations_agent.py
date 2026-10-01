from database import list_products, find_supplier_for_product
from runtime import crew_json
from crewai_tools import get_inventory_tools


def inventory_snapshot(business_id=1):
    rows = []
    for p in list_products(business_id):
        rows.append({"id": p["id"], "name": p["name"], "stock": p["stock_quantity"], "minimum_stock": p["minimum_stock"], "unit": p["unit"], "low_stock": p["stock_quantity"] <= p["minimum_stock"]})
    return rows


def low_stock_items(business_id=1):
    return [x for x in inventory_snapshot(business_id) if x["low_stock"]]


def supplier_draft(product_id, business_id=1, quantity=None, created_by=0):
    product = next((p for p in list_products(business_id) if p["id"] == product_id), None)
    if not product:
        raise ValueError("Product not found.")
    supplier = find_supplier_for_product(product_id, business_id)
    if not supplier:
        raise ValueError("No supplier is configured for this product.")
    suggested = quantity if quantity is not None else max(product["minimum_stock"] * 2 - product["stock_quantity"], 1)
    return {"supplier": supplier, "product": product, "suggested_quantity": suggested}


def classify_operation_request(text: str) -> dict:
    q = (text or "").lower()
    fallback = {"intent": "inventory", "reason": "default operational request"}
    if any(x in q for x in ["supplier", "order bana", "reorder", "purchase"]):
        fallback = {"intent": "supplier_order", "reason": "supplier/reorder request"}
    elif any(x in q for x in ["low stock", "kam hai", "stock", "inventory"]):
        fallback = {"intent": "inventory", "reason": "stock request"}
    prompt = f"Classify into exactly one intent: inventory, supplier_order, unknown. Return JSON {{\"intent\":\"...\",\"reason\":\"...\"}}. Request: {text}"
    return crew_json(
        "Operations Agent",
        "Interpret inventory and supplier requests and select the correct deterministic workflow.",
        "You are responsible for stock and supplier workflows. Never invent stock, prices, or supplier facts.",
        prompt,
        fallback=fallback,
        tools=get_inventory_tools(),
    )
