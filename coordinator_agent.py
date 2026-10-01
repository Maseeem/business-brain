import json
from runtime import crew_json

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


def route_request(text: str) -> dict:
    fallback = {"route": _fallback_route(text), "reason": "deterministic fallback"}
    prompt = f"""Classify the shopkeeper request into exactly one route: sale, receipt, operations, knowledge, unknown.
Examples: '1 Pepsi aur 2 tissue' => sale; 'receipt check karo' => receipt; 'Flour kam hai?' => operations; 'refund policy kya hai?' => knowledge.
Return only JSON: {{"route":"sale|receipt|operations|knowledge|unknown","reason":"short"}}.
Request: {text}"""
    try:
        data = crew_json(
            "Coordinator Agent",
            "Route each shopkeeper request to exactly one specialized workflow without solving it.",
            "You are the front-door coordinator of Business Brain. You route work and never invent business facts.",
            prompt,
            fallback=fallback,
        )
        route = data.get("route", "unknown")
        if route not in ROUTES:
            route = "unknown"
        return {"route": route, "reason": str(data.get("reason", ""))[:240]}
    except Exception:
        return fallback
