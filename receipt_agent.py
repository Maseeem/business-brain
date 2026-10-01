import json
import os
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from agent_runtime import crew_json


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _match_expected(name, expected_items):
    name = str(name or "").strip().lower()
    if not name:
        return None
    best = None
    best_score = 0.0
    for item in expected_items:
        candidate = str(item.get("name", "")).strip().lower()
        score = SequenceMatcher(None, name, candidate).ratio()
        if name == candidate:
            return item
        if candidate in name or name in candidate:
            score = max(score, 0.9)
        if score > best_score:
            best_score, best = score, item
    return best if best_score >= 0.62 else None


def compare_receipt_to_order(extracted: dict, expected_items: list, expected_total) -> dict:
    """Deterministically compare OCR/vision extraction with the saved sale."""
    mismatches = []
    receipt_items = extracted.get("items") if isinstance(extracted, dict) else None
    receipt_items = receipt_items if isinstance(receipt_items, list) else []
    if not receipt_items:
        mismatches.append({"type": "unclear", "message": "I couldn't read the receipt items clearly. Please verify manually."})
        return {"status": "Unclear", "mismatches": mismatches}

    matched_expected = set()
    for receipt_item in receipt_items:
        name = str(receipt_item.get("name", "")).strip()
        expected = _match_expected(name, expected_items)
        if not expected:
            mismatches.append({"type": "extra", "message": f"Receipt contains an item that could not be matched to the saved order: {name or 'Unknown item'}."})
            continue
        matched_expected.add(expected["product_id"] if "product_id" in expected else expected["name"])
        rq = _to_decimal(receipt_item.get("quantity"))
        eq = _to_decimal(expected.get("quantity"))
        if rq is None:
            mismatches.append({"type": "unclear", "message": f"Quantity for {expected['name']} could not be read clearly."})
        elif eq is not None and rq != eq:
            mismatches.append({"type": "quantity", "message": f"Possible quantity mismatch for {expected['name']}: expected {expected['quantity']}, receipt shows {receipt_item.get('quantity')}."})

        rp = _to_decimal(receipt_item.get("unit_price"))
        ep = _to_decimal(expected.get("unit_price"))
        if rp is None:
            mismatches.append({"type": "unclear", "message": f"Price for {expected['name']} could not be read clearly."})
        elif ep is not None and rp != ep:
            mismatches.append({"type": "price", "message": f"Possible price mismatch for {expected['name']}: expected Rs. {ep:.2f}, receipt shows Rs. {rp:.2f}."})

    for expected in expected_items:
        key = expected.get("product_id", expected.get("name"))
        if key not in matched_expected:
            mismatches.append({"type": "missing", "message": f"{expected['name']} appears to be missing from the receipt."})

    receipt_total = _to_decimal(extracted.get("total"))
    expected_total_dec = _to_decimal(expected_total)
    if receipt_total is None:
        mismatches.append({"type": "unclear", "message": "The receipt total could not be read clearly."})
    elif expected_total_dec is not None and receipt_total != expected_total_dec:
        mismatches.append({"type": "total", "message": f"Possible total mismatch: expected Rs. {expected_total_dec:.2f}, receipt shows Rs. {receipt_total:.2f}."})

    status = "Match" if not mismatches else ("Unclear" if all(x["type"] == "unclear" for x in mismatches) else "Possible mismatch")
    return {"status": status, "mismatches": mismatches}


def _extract_receipt_with_gemini(image_bytes: bytes, mime_type: str) -> dict:
    from google import genai
    from google.genai import types
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    client = genai.Client(api_key=key)
    prompt = """Read this receipt and extract ONLY information visibly present.
Return JSON with this exact shape:
{"items":[{"name":"","quantity":0,"unit_price":0}],"total":0}
If a field is unreadable, use null. Do not calculate or guess missing values. Do not decide whether it matches another order."""
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
        config=types.GenerateContentConfig(max_output_tokens=2500, response_mime_type="application/json"),
    )
    text = getattr(response, "text", "") or ""
    return json.loads(text)


def verify_receipt(image_bytes: bytes, mime_type: str, expected_items: list, expected_total: float) -> dict:
    """Execute the Receipt Agent layer, then Vision extraction and Python comparison."""
    fallback = {"action": "extract_and_compare"}
    prompt = """You are the Business Brain Receipt Agent.
Prepare the receipt-verification workflow. Return JSON only: {"action":"extract_and_compare"}.
Do not calculate totals and do not decide whether the receipt matches.
Gemini Vision extracts visible fields; deterministic Python compares them to the saved order."""
    plan = crew_json(
        "Receipt Agent",
        "Orchestrate receipt extraction and deterministic verification.",
        "You are a receipt-verification specialist. Vision reads the document; Python is the authority for all financial comparison.",
        prompt,
        fallback=fallback,
    )
    if not isinstance(plan, dict) or plan.get("action") != "extract_and_compare":
        plan = fallback
    extracted = _extract_receipt_with_gemini(image_bytes, mime_type)
    comparison = compare_receipt_to_order(extracted, expected_items, expected_total)
    return {"extracted": extracted, **comparison, "agent": "receipt", "agent_plan": plan}
