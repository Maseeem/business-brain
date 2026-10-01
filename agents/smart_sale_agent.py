import json
import re
from product_tools import find_product_tool
from cart_tools import create_cart, add_item, calculate_subtotal, calculate_total
from database import list_products

NUMBER_WORDS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "ek":1,"aik":1,"do":2,"du":2,"teen":3,"tin":3,"char":4,"chaar":4,"paanch":5,"panch":5,"che":6,"chay":6,"saat":7,"aath":8,"nau":9,"das":10,
    "ایک":1,"اک":1,"دو":2,"تین":3,"تِن":3,"چار":4,"پانچ":5,"چھ":6,"سات":7,"آٹھ":8,"آٹھ":8,"نو":9,"دس":10,"دونوں":2,
}

def _normalize_digits(text):
    return str(text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def _words_to_number(text):
    t=_normalize_digits(text).strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?",t): return float(t)
    return float(NUMBER_WORDS[t]) if t in NUMBER_WORDS else None

def _norm(s):
    s=_normalize_digits(s).lower()
    return re.sub(r"[^\w\s-]", " ", s, flags=re.UNICODE).strip()

def _fallback_extract(text, catalog):
    q=_norm(text)
    found=[]
    ordered=sorted(catalog,key=lambda p:max([len(_norm(p["name"]))]+[len(_norm(a)) for a in str(p.get("aliases","")).split(",") if a.strip()]),reverse=True)
    number_pattern=r"(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|ek|aik|do|du|teen|tin|char|chaar|paanch|panch|che|chay|saat|aath|nau|das|ایک|اک|دو|تین|تِن|چار|پانچ|چھ|سات|آٹھ|آٹھ|نو|دس|دونوں)"
    unit_pattern=r"(?:kg|kilo|kilos|kilogram|kilograms|کلو|کلوگرام|liter|litre|ltr|لٹر|لیٹر|pcs|piece|pieces|pack|packs|پیک|پیکٹ)?"
    for product in ordered:
        aliases=[product["name"]]+[a.strip() for a in str(product.get("aliases","")).split(",") if a.strip()]
        matched=None
        for alias in sorted(aliases,key=len,reverse=True):
            a=_norm(alias)
            if a and re.search(rf"(?<!\w){re.escape(a)}(?!\w)",q):
                matched=a; break
        if not matched: continue
        qty=1.0
        # Quantity immediately before product, including Urdu/Roman Urdu words.
        pats=[
            rf"({number_pattern})\s*{unit_pattern}\s*{re.escape(matched)}",
            rf"({number_pattern})\s*{re.escape(matched)}",
            rf"{re.escape(matched)}\s*(?:x|×)?\s*({number_pattern})",
        ]
        for pat in pats:
            m=re.search(pat,q)
            if m:
                n=_words_to_number(m.group(1))
                if n is not None: qty=n
                break
        found.append({"product_id":product["id"],"quantity":qty})
    return {"items":found}

def extract_order(text: str, business_id: int = 1) -> dict:
    catalog=[{"id":p["id"],"name":p["name"],"aliases":p.get("aliases","") or "","unit":p.get("unit","unit")} for p in list_products(business_id)]
    # Deterministic product/quantity extraction is the source of truth. Do not let an LLM replace
    # a clearly matched product with an unrelated hallucinated product.
    return {"items":[{"product":next(p for p in catalog if p["id"]==x["product_id"]),"quantity":x["quantity"]} for x in _fallback_extract(text,catalog)["items"]]}

def build_cart(text: str, business_id: int = 1) -> dict:
    parsed=extract_order(text,business_id); cart=create_cart(); missing_price=[]
    for item in parsed["items"]:
        product=find_product_tool(item["product"]["name"],business_id)
        if not product: continue
        price=product.get("price")
        qty=float(item["quantity"])
        stock=float(product.get("stock_quantity",0) or 0)
        cart.append({
            "product_id":product["id"],"name":product["name"],"quantity":qty,
            "unit_price":(float(price) if price is not None else None),
            "subtotal":(calculate_subtotal(qty,float(price)) if price is not None else None),
            "unit":product.get("unit","unit"),"stock_quantity":stock,
        })
        if price is None: missing_price.append(product["name"])
    priced=[x for x in cart if x.get("subtotal") is not None]
    total=round(sum(x["subtotal"] for x in priced),2) if priced else 0.0
    return {"cart":cart,"total":total,"missing_price":missing_price,"parsed_items":parsed["items"]}

def apply_cart_edit(cart, action: str, business_id: int = 1) -> dict:
    parsed=extract_order(action,business_id)
    if not parsed["items"]: return {"cart":cart,"total":0.0,"changed":False}
    new=list(cart)
    changed=False
    for item in parsed["items"]:
        pid=item["product"]["id"]; qty=float(item["quantity"])
        existing=next((x for x in new if x["product_id"]==pid),None)
        product=find_product_tool(item["product"]["name"],business_id)
        if existing:
            existing["quantity"]=qty
            existing["subtotal"]=(qty*existing["unit_price"] if existing.get("unit_price") is not None else None)
            existing["stock_quantity"]=float(product.get("stock_quantity",0) or 0) if product else existing.get("stock_quantity",0)
            changed=True
        elif product:
            price=product.get("price")
            new.append({"product_id":product["id"],"name":product["name"],"quantity":qty,"unit_price":(float(price) if price is not None else None),"subtotal":(qty*float(price) if price is not None else None),"unit":product.get("unit","unit"),"stock_quantity":float(product.get("stock_quantity",0) or 0)})
            changed=True
    total=round(sum(x["subtotal"] for x in new if x.get("subtotal") is not None),2)
    return {"cart":new,"total":total,"changed":changed}
