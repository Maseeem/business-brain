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


def route_request(text: str, business_id: int = 1) -> dict:
    """Route safely. If the text contains a known catalog product, treat it as a sale.
    This prevents the coordinator LLM from turning ordinary Urdu orders into unknown requests.
    """
    q = (text or "").lower()
    if any(x in q for x in ["receipt", "رسید", "verify"]):
        return {"route":"receipt","reason":"receipt workflow keyword"}
    if any(x in q for x in ["policy", "refund", "procedure", "process", "rule"]):
        return {"route":"knowledge","reason":"knowledge workflow keyword"}
    try:
        from database import list_products
        for p in list_products(business_id):
            terms=[p.get("name","")]+[a.strip() for a in str(p.get("aliases","")).split(",") if a.strip()]
            if any(t and t.lower() in q for t in terms):
                return {"route":"sale","reason":"known catalog product detected"}
    except Exception:
        pass
    if any(x in q for x in ["stock", "inventory", "supplier", "low stock"]):
        return {"route":"operations","reason":"operations workflow keyword"}
    if any(x in q for x in ["sale", "sell", "buy", "chahiye", "چاہیے", "دو کلو", "ایک کلو"]):
        return {"route":"sale","reason":"sale language detected"}
    return {"route":"unknown","reason":"no matching workflow"}
