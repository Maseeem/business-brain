import json
from agent_runtime import crew_json

ROUTES = {"sale", "receipt", "operations", "knowledge", "unknown"}


def _fallback_route(text: str):
    q = (text or "").lower()
    if any(x in q for x in ["receipt", "رسید", "verify"]):
        return "receipt"
    if any(x in q for x in ["stock", "inventory", "supplier", "order bana", "low stock", "flour ka stock"]):
        return "operations"
    if any(x in q for x in ["policy", "refund", "procedure", "process", "rule"]):
        return "knowledge"
    if any(x in q for x in ["pepsi", "tissue", "surf", "flour", "sale", "sell", "buy", "chahiye"]):
        return "sale"
    return "unknown"



def _deterministic_route(text: str, business_id: int = 1) -> str:
    """Safe fallback router used when the LLM/CrewAI router is unavailable."""
    text = (text or "").strip().lower()

    receipt_words = [
        "receipt", "bill", "invoice", "رسید", "بل", "تصویر", "photo", "upload"
    ]
    knowledge_words = [
        "policy", "refund", "procedure", "process", "rule", "sop",
        "policy kya", "کیا طریقہ", "پالیسی", "قانون", "طریقہ"
    ]
    operations_words = [
        "stock", "inventory", "low stock", "restock", "supplier",
        "reorder", "order from supplier", "سٹاک", "انوینٹری", "سپلائر",
        "دوبارہ منگوا", "کم سٹاک"
    ]
    sale_words = [
        "sale", "sell", "buy", "chahiye", "need", "cart", "order",
        "خرید", "چاہیے", "لینا", "دو", "دیں"
    ]

    if any(k in text for k in receipt_words):
        return "receipt"

    if any(k in text for k in knowledge_words):
        return "knowledge"

    if any(k in text for k in operations_words):
        return "operations"

    # Product/catalog evidence is a strong sale signal.
    try:
        products = list_products(business_id)
        for p in products:
            hay = " ".join(
                str(p.get(k, "")) for k in ("name", "aliases", "sku")
            ).lower()
            if hay and any(token in text for token in hay.split(",") if token.strip()):
                return "sale"
    except Exception:
        pass

    if any(k in text for k in sale_words):
        return "sale"

    return "unknown"


def route_request(text: str, business_id: int = 1) -> str:
    """
    CrewAI-first Coordinator Agent.

    The Coordinator is the entry point for natural-language requests.
    It asks the LLM to select one specialized Business Brain agent and
    validates the result against the allowed routes. If the LLM/CrewAI
    call fails or returns an invalid route, the deterministic router keeps
    the application usable.
    """
    prompt = f"""
You are the Coordinator Agent for Business Brain, a multi-agent shop
operations assistant.

Choose exactly ONE route for this user request:

- sale: product purchase/sale, cart, quantity, product price, new order
- receipt: receipt/bill/invoice image upload, receipt checking or verification
- operations: inventory, stock, low-stock, restocking, supplier, reorder
- knowledge: business policies, SOPs, procedures, rules, business knowledge
- unknown: anything that does not clearly belong to the above

Rules:
1. Return ONLY one word: sale, receipt, operations, knowledge, or unknown.
2. Do not answer the user.
3. Do not invent business facts.
4. Prefer the most specific route.
5. Current business_id is {business_id}.

User request:
{text}
""".strip()

    try:
        result = crew_json(
            agent_role="Business Brain Coordinator Agent",
            task_description=prompt,
            expected_schema={
                "route": "sale | receipt | operations | knowledge | unknown"
            },
        )

        route = str(result.get("route", "")).strip().lower()
        if route in ROUTES:
            return route
    except Exception:
        pass

    return _deterministic_route(text, business_id)
