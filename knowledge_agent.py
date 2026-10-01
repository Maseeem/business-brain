"""Knowledge Agent: specialized layer over the existing Business Brain RAG."""
from agent import _generate
from rag import retrieve, format_context, contradictions_for_results
from agent_runtime import crew_json


def _retrieval_query(question: str) -> str:
    """Normalize common Roman Urdu phrasing into searchable Business Brain terms."""
    q = (question or "").strip()
    replacements = {
        "hamari order process": "our order process order workflow",
        "order process kya hai": "order process workflow",
        "customer complaint kaun handle karta hai": "customer complaint who handles responsibilities customer service manager",
        "kaun handle karta hai": "who handles responsibilities",
        "kis ki zimmedari": "responsibility who handles",
        "refund policy kya hai": "refund policy",
        "process kya hai": "process workflow",
        "policy kya hai": "policy",
    }
    lowered = q.casefold()
    for phrase, replacement in replacements.items():
        if phrase in lowered:
            return f"{q} {replacement}"
    return q


def _agent_plan(question: str, business_id=1) -> dict:
    """Use the real CrewAI Knowledge Agent for retrieval planning only.

    The agent may normalize the search query, but it is never trusted to invent
    business facts or generate the final answer. RAG remains the evidence source.
    """
    fallback = {"action": "retrieve", "query": _retrieval_query(question)}
    prompt = f"""You are the Business Brain Knowledge Agent.
Prepare a retrieval plan for the user's business-knowledge question.
Return JSON only: {{"action":"retrieve","query":"..."}}
Rules:
- Only prepare a search query; do not answer the user.
- Preserve the user's intent and important business terms.
- Do not invent policies, SOPs, responsibilities, refunds, or company facts.
Business ID: {business_id}
Question: {question}"""
    result = crew_json(
        "Knowledge Agent",
        "Prepare grounded retrieval plans for Business Brain knowledge questions.",
        "You are a knowledge specialist. RAG documents are the only source of business truth; you never invent facts.",
        prompt,
        fallback=fallback,
    )
    if not isinstance(result, dict) or result.get("action") != "retrieve":
        return fallback
    query = str(result.get("query") or "").strip()
    return {"action": "retrieve", "query": query or fallback["query"]}


def answer(question: str, conversation=None, business_id=1):
    """Execute the Knowledge Agent, then ground the answer in the existing RAG."""
    plan = _agent_plan(question, business_id)
    try:
        results = retrieve(plan["query"], top_k=6, business_id=business_id)
    except TypeError:
        # Backward compatibility with older RAG signatures.
        results = retrieve(question, top_k=6)
        results = [r for r in results if r.get("business_id", business_id) == business_id]
    if not results:
        return {"ok": True, "answer": "I couldn't find enough information in your Business Brain to answer this confidently.", "sources": []}

    conflicts = contradictions_for_results(results)
    conflict_instruction = ""
    if conflicts:
        conflict_instruction = "\nStored sources may conflict. Explicitly flag any conflict; do not silently choose one source.\n" + "\n".join(
            f"- {x['a_title']} conflicts with {x['b_title']}: {x['reason']}" for x in conflicts
        )
    prompt = f"""You are the Business Brain Knowledge Agent.
Answer ONLY from the retrieved Business Brain sources below.
Do not invent policies, SOPs, responsibilities, refunds, company facts, prices, or procedures.
If evidence is incomplete, say so.
User question: {question}
Retrieved sources:
{format_context(results)}
{conflict_instruction}
"""
    try:
        response = _generate(prompt)
    except Exception as exc:
        return {"ok": False, "error": "Knowledge search is temporarily unavailable."}

    sources=[]
    seen=set()
    for r in results:
        key=(r.get("source_type"),r.get("source_id"),r.get("title"))
        if key in seen: continue
        seen.add(key)
        sources.append({"title":r.get("title"),"type":str(r.get("source_type","knowledge")).title(),"score":r.get("score"),"content":str(r.get("content",""))[:360]})
    return {"ok": True, "answer": response, "sources": sources, "conflicts": conflicts}
