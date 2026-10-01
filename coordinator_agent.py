"""Coordinator Agent: CrewAI-first routing with deterministic safety fallback."""
from agent_runtime import crew_json

ROUTES = {"sale", "receipt", "operations", "knowledge", "unknown"}


def _fallback_route(text: str, business_id: int = 1):
    q = (text or "").strip().lower()
    if any(x in q for x in ["receipt", "رسید", "verify receipt", "receipt check", "bill check", "invoice check"]):
        return "receipt"
    if any(x in q for x in [
        "stock", "inventory", "low stock", "supplier", "vendor", "reorder", "purchase",
        "order bana", "order banado", "order bna", "sales", "sale total", "revenue",
        "orders kitne", "kitne orders", "today sales", "aaj ki sales", "last 7", "pichlay 7",
        "price", "rate", "qeemat", "قیمت", "supplier kaun", "kis supplier",
        "اسٹاک", "انوینٹری", "سپلائر", "کم اسٹاک",
    ]):
        return "operations"
    if any(x in q for x in [
        "policy", "refund", "procedure", "process", "rule", "sop", "responsibility",
        "who handles", "kaun handle", "kis ki zimmedari", "knowledge", "guide", "faq",
        "policy kya", "process kya", "procedure kya",
    ]):
        return "knowledge"
    if any(x in q for x in ["sale", "sell", "buy", "chahiye", "چاہیے", "cart", "lena"]):
        return "sale"
    try:
        from database import list_products
        for product in list_products(business_id):
            names=[product.get("name","")] + [x.strip() for x in str(product.get("aliases","")).split(",") if x.strip()]
            if any(name and name.lower() in q for name in names):
                return "sale"
    except Exception:
        pass
    return "unknown"


def route_request(text: str, business_id: int = 1) -> dict:
    q=(text or "").strip()
    fallback_route=_fallback_route(q,business_id)
    fallback={"route":fallback_route,"reason":{
        "sale":"sale/order request detected",
        "receipt":"receipt verification request detected",
        "operations":"live operational query detected",
        "knowledge":"stored business knowledge query detected",
        "unknown":"no supported workflow detected",
    }[fallback_route]}
    if not q: return fallback

    prompt=f"""You are the Business Brain Coordinator Agent.
Route the request to exactly one specialized agent: sale, receipt, operations, knowledge, unknown.
Return JSON only: {{"route":"...","reason":"short reason"}}
Rules:
- Live inventory, stock, low-stock, product price, sales totals/counts, suppliers, reorder or supplier-order drafting -> operations.
- Receipt/bill/invoice verification -> receipt.
- Stored business policies, SOPs, procedures, responsibilities, process/document questions -> knowledge.
- Customer product order/sale/cart request -> sale.
- Unclear/unrelated -> unknown.
Never answer the request and never mutate data.
Business ID: {business_id}
Request: {q}"""
    result=crew_json(
        "Coordinator Agent",
        "Route each Business Brain request to the correct specialized agent.",
        "You are a strict routing coordinator. Live facts must never be answered from RAG and product names in operational questions must not become sales routes.",
        prompt,
        fallback=fallback,
    )
    if not isinstance(result,dict): return fallback
    route=str(result.get("route","unknown")).strip().lower()
    if route not in ROUTES: return fallback
    # High-confidence safety guard: live/receipt workflows must never be misrouted.
    if fallback_route in {"operations","receipt"} and route != fallback_route:
        return fallback
    return {"route":route,"reason":str(result.get("reason") or fallback["reason"])}
