import json
import re
from difflib import SequenceMatcher
from product_tools import find_product_tool
from cart_tools import create_cart, add_item, change_quantity, calculate_total
from agent_runtime import crew_json
from crewai_tools import get_product_tools

NUMBER_WORDS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "ek":1,"aik":1,"do":2,"du":2,"teen":3,"tin":3,"char":4,"chaar":4,"paanch":5,"panch":5,"che":6,"chay":6,
    "saat":7,"aath":8,"nau":9,"das":10,
    "ایک":1,"اک":1,"دو":2,"تین":3,"چار":4,"پانچ":5,"چھ":6,"سات":7,"آٹھ":8,"آٹھ":8,"نو":9,"دس":10,
}

def _normalize_digits(text):
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return str(text or "").translate(table)

def _words_to_number(text):
    t=_normalize_digits(text).strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?",t): return float(t)
    return float(NUMBER_WORDS[t]) if t in NUMBER_WORDS else None

def _norm(s):
    s = _normalize_digits(s)
    return re.sub(r"[^\w\s-]", " ", str(s or "").lower(), flags=re.UNICODE).strip()

def _product_match(fragment, product):
    f=_norm(fragment); names=[_norm(product["name"])] + [_norm(x) for x in str(product.get("aliases","")).split(",") if x.strip()]
    return any(n and (n in f or f in n) for n in names)

def _fallback_extract(text, catalog):
    q=_norm(text)
    found=[]
    # Longest names first so "cooking oil" wins over "oil".
    ordered=sorted(catalog,key=lambda p:max(len(_norm(p["name"])),len(str(p.get("aliases","")).split(",")[0])),reverse=True)
    for p in ordered:
        aliases=[p["name"]]+[a.strip() for a in str(p.get("aliases","")).split(",") if a.strip()]
        matched=None
        for alias in sorted(aliases,key=len,reverse=True):
            a=_norm(alias)
            if a and re.search(rf"(?<!\w){re.escape(a)}(?!\w)",q):
                matched=a; break
        if not matched: continue
        qty=1.0
        # quantity before product: "2 kg atta", "do kilo sooji"
        patterns=[
            rf"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilos|kilogram|kilograms|کلو|کلوگرام|liter|litre|ltr|لیٹر|لٹر|pcs|piece|pieces|pack|packs|پیک|پیکٹ)?\s*{re.escape(matched)}",
            rf"\b(one|two|three|four|five|six|seven|eight|nine|ten|ek|aik|do|du|teen|tin|char|chaar|paanch|panch|che|chay|saat|aath|nau|das|ایک|اک|دو|تین|چار|پانچ|چھ|سات|آٹھ|آٹھ|نو|دس)\s*(?:kg|kilo|kilos|kilogram|kilograms|کلو|کلوگرام|liter|litre|ltr|لیٹر|لٹر|pcs|piece|pieces|pack|packs|پیک|پیکٹ)?\s*{re.escape(matched)}",
            rf"{re.escape(matched)}\s*(?:x|×)?\s*(\d+(?:\.\d+)?)",
            rf"{re.escape(matched)}\s*(?:x|×)?\s*(one|two|three|four|five|six|seven|eight|nine|ten|ek|aik|do|du|teen|tin|char|chaar|paanch|panch|che|chay|saat|aath|nau|das|ایک|اک|دو|تین|چار|پانچ|چھ|سات|آٹھ|آٹھ|نو|دس)",
        ]
        for pat in patterns:
            m=re.search(pat,q)
            if m:
                n=_words_to_number(m.group(1));
                if n is not None: qty=n
                break
        found.append({"product_id":p["id"],"quantity":qty})
    # If parser found products, avoid duplicate matches.
    ded={x["product_id"]:x for x in found}
    return {"items":list(ded.values())}

def extract_order(text: str, business_id: int = 1) -> dict:
    from database import list_products
    catalog=[{"id":p["id"],"name":p["name"],"aliases":p.get("aliases","") or "","unit":p.get("unit","unit")} for p in list_products(business_id)]
    fallback=_fallback_extract(text,catalog)
    prompt=f"""Extract a shop order into JSON. Use ONLY product IDs from this catalogue:\n{json.dumps(catalog,ensure_ascii=False)}\nSupport English, Urdu and Roman Urdu number words. Quantity must be numeric and greater than zero. Do not invent products or prices. Return only {{\"items\":[{{\"product_id\":1,\"quantity\":2}}]}}.\nOrder: {text}"""
    data=crew_json("Smart Sale Agent","Extract products and quantities only from the supplied shop catalogue.","You are a sales extraction specialist. Never invent product identity or price.",prompt,fallback=fallback,tools=get_product_tools())
    products=[]; valid_ids={p["id"]:p for p in catalog}
    for item in data.get("items",[]) if isinstance(data,dict) else []:
        try: pid=int(item["product_id"]); qty=float(item["quantity"])
        except (KeyError,TypeError,ValueError): continue
        if pid in valid_ids and qty>0: products.append({"product":valid_ids[pid],"quantity":qty})
    # Deterministic fallback is the source of truth if LLM dropped catalogue matches.
    llm_ids={x["product"]["id"] for x in products}
    for x in fallback["items"]:
        if x["product_id"] not in llm_ids:
            products.append({"product":valid_ids[x["product_id"]],"quantity":x["quantity"]})
    return {"items":products}

def build_cart(text: str, business_id: int = 1) -> dict:
    parsed=extract_order(text,business_id); cart=create_cart(); missing_price=[]
    for item in parsed["items"]:
        product=find_product_tool(item["product"]["name"],business_id)
        if not product: continue
        if product.get("price") is None: missing_price.append(product["name"]); continue
        add_item(cart,product,item["quantity"])
    return {"cart":cart,"total":calculate_total(cart),"missing_price":missing_price,"parsed_items":parsed["items"]}

def apply_cart_edit(cart, action: str, business_id: int = 1) -> dict:
    parsed=extract_order(action,business_id)
    if not parsed["items"]: return {"cart":cart,"total":calculate_total(cart),"changed":False}
    for item in parsed["items"]:
        pid=item["product"]["id"]; existing=next((x for x in cart if x["product_id"]==pid),None)
        if existing: change_quantity(cart,pid,item["quantity"])
        else:
            product=find_product_tool(item["product"]["name"],business_id)
            if product and product.get("price") is not None: add_item(cart,product,item["quantity"])
    return {"cart":cart,"total":calculate_total(cart),"changed":True}
