"""Business Brain Coordinator Agent.

The coordinator is a real CrewAI agent: it decides which specialist workflow should
handle a request. Deterministic catalog/keyword checks are kept only as a safe
fallback so the app still works if Groq/CrewAI is temporarily unavailable.
"""
import json
import re
from agent_runtime import crew_json

ROUTES = {"sale", "receipt", "operations", "knowledge", "unknown"}


def _catalog_context(business_id: int) -> str:
    try:
        from database import list_products
        rows = list_products(business_id)
        parts = []
        for p in rows[:100]:
            aliases = [a.strip() for a in str(p.get("aliases", "")).split(",") if a.strip()]
            parts.append(f"{p.get('name','')} | aliases: {', '.join(aliases)}")
        return "\n".join(parts)
    except Exception:
        return ""


def _fallback_route(text: str, business_id: int = 1):
    q = (text or "").lower()
    if any(x in q for x in ["receipt", "رسید", "verify", "invoice", "bill"]):
        return "receipt", "receipt workflow detected"
    if any(x in q for x in ["policy", "refund", "procedure", "process", "rule", "sop", "knowledge"]):
        return "knowledge", "knowledge workflow detected"
    try:
        from database import list_products
        for p in list_products(business_id):
            terms = [p.get("name", "")] + [a.strip() for a in str(p.get("aliases", "")).split(",") if a.strip()]
            if any(t and t.lower() in q for t in terms):
                return "sale", "known catalog product detected"
    except Exception:
        pass
    if any(x in q for x in ["stock", "inventory", "supplier", "low stock", "reorder", "restock", "order bana"]):
        return "operations", "operations workflow detected"
    if any(x in q for x in ["sale", "sell", "buy", "chahiye", "چاہیے", "کلو", "quantity", "price"]):
        return "sale", "sales workflow detected"
    return "unknown", "no specialist workflow detected"


def route_request(text: str, business_id: int = 1) -> dict:
    """Use the Coordinator Agent to route a request to one specialist.

    CrewAI/Groq is the primary router. The fallback is deterministic and never
    replaces a valid catalog match when the LLM is unavailable.
    """
    fallback_route, fallback_reason = _fallback_route(text, business_id)
    catalog = _catalog_context(business_id)
    prompt = f"""
You are the Coordinator Agent for a small-shop Business Brain.
Route the user's request to exactly ONE specialist:
- sale: product purchase/sale/order, product price, quantity, cart
- receipt: receipt/invoice image checking or verification
- operations: stock, inventory, low stock, restock, supplier, reorder
- knowledge: business policies, SOPs, procedures, responsibilities, stored documents
- unknown: genuinely unrelated or unclear requests

Never invent facts. Do not answer the business question yourself.
Return ONLY JSON: {{"route":"sale|receipt|operations|knowledge|unknown","reason":"short reason"}}

Business catalog (names and aliases only):
{catalog or '(catalog unavailable)'}

User request:
{text}
"""
    try:
        result = crew_json(
            role="Coordinator Agent",
            goal="Route every business request to the correct specialist agent.",
            backstory=(
                "You are the central dispatcher of Business Brain. You do not perform the specialist task; "
                "you select the correct specialist and keep the workflow grounded in the shop's real catalog."
            ),
            prompt=prompt,
            fallback={"route": fallback_route, "reason": fallback_reason},
        )
        route = str(result.get("route", "unknown")).strip().lower()
        if route not in ROUTES:
            route, reason = fallback_route, fallback_reason
        else:
            reason = str(result.get("reason", "Coordinator selected specialist"))
        return {"route": route, "reason": reason, "agent": "Coordinator Agent", "crew_ai": True}
    except Exception:
        return {"route": fallback_route, "reason": fallback_reason, "agent": "Coordinator Agent", "crew_ai": False}
