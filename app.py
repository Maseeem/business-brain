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
    """Safe fallback when CrewAI/Groq is unavailable."""
    text = (text or "").strip().lower()

    receipt_words = [
        "receipt", "bill", "invoice", "رسید", "بل", "تصویر", "photo", "upload"
    ]
    knowledge_words = [
        "policy", "refund", "procedure", "process", "rule", "sop",
        "پالیسی", "قانون", "طریقہ"
    ]
    operations_words = [
        "stock", "inventory", "low stock", "restock", "supplier",
        "reorder", "purchase", "سٹاک", "انوینٹری", "سپلائر",
        "دوبارہ منگوا", "کم سٹاک"
    ]
    sale_words = [
        "sale", "sell", "buy", "chahiye", "need", "cart", "order",
        "خرید", "چاہیے", "لینا"
    ]

    if any(k in text for k in receipt_words):
        return "receipt"
    if any(k in text for k in knowledge_words):
        return "knowledge"
    if any(k in text for k in operations_words):
        return "operations"

    try:
        products = list_products(business_id)
        for p in products:
            hay = " ".join(
                str(p.get(k, "")) for k in ("name", "aliases", "sku")
            ).lower()
            if any(token.strip() and token.strip() in text for token in hay.split(",")):
                return "sale"
    except Exception:
        pass

    if any(k in text for k in sale_words):
        return "sale"
    return "unknown"


def route_request(text: str, business_id: int = 1) -> dict:
    """
    CrewAI-first Coordinator Agent.

    Returns the same dict shape expected by the existing Streamlit UI:
    {"route": "...", "reason": "..."}.
    """
    prompt = f"""
You are the Coordinator Agent for Business Brain, a multi-agent shop
operations assistant.

Select exactly ONE route:
- sale: product purchase/sale, cart, quantity, product price, new order
- receipt: receipt/bill/invoice image or verification
- operations: inventory, stock, low-stock, restocking, supplier, reorder
- knowledge: business policies, SOPs, procedures, rules, business knowledge
- unknown: anything else

Return ONLY JSON:
{{"route":"sale|receipt|operations|knowledge|unknown","reason":"short reason"}}

Do not answer the user. Do not invent business facts.
Business ID: {business_id}
User request: {text}
""".strip()

    fallback_route = _deterministic_route(text, business_id)
    fallback = {
        "route": fallback_route,
        "reason": "Deterministic safety fallback."
    }

    try:
        result = crew_json(
            role="Business Brain Coordinator Agent",
            goal="Route each user request to exactly one specialized Business Brain agent.",
            backstory=(
                "You coordinate a shop operations system containing Smart Sale, "
                "Receipt, Operations, and Knowledge agents. You never invent "
                "prices, stock, supplier facts, or policies."
            ),
            prompt=prompt,
            fallback=fallback,
        )
        route = str(result.get("route", "")).strip().lower()
        if route in ROUTES:
            return {
                "route": route,
                "reason": str(result.get("reason", "Coordinator selected this route."))
            }
    except Exception:
        pass

    return fallback
