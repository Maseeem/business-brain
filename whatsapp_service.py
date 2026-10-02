"""Isolated WhatsApp Cloud API adapter and deterministic report service."""
import json
import os
import urllib.error
import urllib.request
from datetime import datetime

from database import get_business, get_daily_operations, list_products, list_supplier_orders, query_today_sales


def _secret(name):
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st
        value = str(st.secrets.get(name, "") or "").strip()
        return value
    except Exception:
        return ""


def _config():
    return {
        "access_token": _secret("WHATSAPP_ACCESS_TOKEN"),
        "phone_number_id": _secret("WHATSAPP_PHONE_NUMBER_ID"),
        "business_account_id": _secret("WHATSAPP_BUSINESS_ACCOUNT_ID"),
        "default_recipient": _secret("WHATSAPP_DEFAULT_RECIPIENT"),
    }


def configuration_status():
    cfg = _config()
    missing = [key for key, value in cfg.items() if not value and key != "default_recipient"]
    return {"configured": not missing, "missing": missing, "has_recipient": bool(cfg["default_recipient"])}


def _api_request(path, payload):
    cfg = _config()
    if not cfg["access_token"] or not cfg["phone_number_id"]:
        raise RuntimeError("WhatsApp Cloud API is not configured. Add the required Streamlit secrets or environment variables.")
    url = f"https://graph.facebook.com/v23.0/{cfg['phone_number_id']}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {cfg['access_token']}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            message = detail.get("error", {}).get("message", "WhatsApp API request failed.")
        except Exception:
            message = "WhatsApp API request failed."
        raise RuntimeError(message) from None
    except urllib.error.URLError:
        raise RuntimeError("WhatsApp service could not be reached. Please try again later.") from None


def send_text(recipient, message):
    recipient = str(recipient or "").strip()
    if not recipient:
        raise ValueError("A WhatsApp recipient number is required.")
    if not message.strip():
        raise ValueError("WhatsApp message cannot be empty.")
    return _api_request("messages", {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"preview_url": False, "body": message}})


def send_template(recipient, template_name, language_code="en_US", components=None):
    return _api_request("messages", {
        "messaging_product": "whatsapp", "to": recipient, "type": "template",
        "template": {"name": template_name, "language": {"code": language_code}, **({"components": components} if components else {})},
    })



def _multipart_request(path, fields, file_field, filename, file_bytes, mime_type="application/pdf"):
    cfg = _config()
    if not cfg["access_token"] or not cfg["phone_number_id"]:
        raise RuntimeError("WhatsApp Cloud API is not configured.")
    boundary = "----BusinessBrainBoundary"
    chunks = []
    for key, value in fields.items():
        chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(), str(value).encode(), b"\r\n"]
    chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(), f"Content-Type: {mime_type}\r\n\r\n".encode(), file_bytes, b"\r\n", f"--{boundary}--\r\n".encode()]
    req = urllib.request.Request(f"https://graph.facebook.com/v23.0/{cfg['phone_number_id']}/{path.lstrip('/')}", data=b"".join(chunks), headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise RuntimeError("WhatsApp document upload failed. Please check the WhatsApp configuration and media permissions.") from None
    except urllib.error.URLError:
        raise RuntimeError("WhatsApp service could not be reached. Please try again later.") from None


def send_document(recipient, pdf_bytes, filename):
    upload = _multipart_request("media", {"messaging_product": "whatsapp"}, "file", filename, pdf_bytes)
    media_id = upload.get("id")
    if not media_id:
        raise RuntimeError("WhatsApp did not return a media ID for the PDF report.")
    return _api_request("messages", {"messaging_product": "whatsapp", "to": str(recipient).strip(), "type": "document", "document": {"id": media_id, "filename": filename}})

def test_connection(recipient=None):
    cfg = _config()
    target = recipient or cfg["default_recipient"]
    result = send_text(target, "Business Brain WhatsApp test successful.")
    return {"ok": True, "message_id": (result.get("messages") or [{}])[0].get("id")}


def _money(value):
    return f"Rs. {float(value or 0):,.2f}"


def build_daily_report(role, business_id, report_date=None, categories=None):
    """Deterministic, role-filtered daily report from SQLite."""
    report_date = report_date or datetime.now().date().isoformat()
    business = get_business(business_id) or {"name": "Business Brain", "profile": ""}
    products = list_products(business_id)
    ops = get_daily_operations(business_id)
    today = query_today_sales(business_id)
    low = [p for p in products if float(p.get("stock_quantity", 0) or 0) <= float(p.get("minimum_stock", 0) or 0)]
    missing = [p for p in products if p.get("price") is None]
    out = [p for p in products if float(p.get("stock_quantity", 0) or 0) <= 0]
    supplier_orders = list_supplier_orders(business_id, 100)
    pending_suppliers = [o for o in supplier_orders if o.get("status") in ("Draft", "Pending Approval")]
    role = str(role or "Employee")
    allowed_categories = {"sales", "inventory", "supplier", "receipts", "activity"}
    categories = {str(c) for c in (categories or []) if str(c) in allowed_categories}
    if not categories:
        categories = allowed_categories
    report = {"business": business, "date": report_date, "generated_at": datetime.now().isoformat(timespec="seconds"), "role": role}
    if role in ("Owner", "Admin"):
        report.update({"sales": today if "sales" in categories else {"sales_total": 0, "order_count": 0}, "orders": today["order_count"] if "sales" in categories else 0,
                       "low_stock": low if "inventory" in categories else [], "inventory": products if "inventory" in categories else [],
                       "missing_price": missing if "inventory" in categories else [], "out_of_stock": out if "inventory" in categories else [],
                       "supplier_orders": supplier_orders if "supplier" in categories else [],
                       "pending_approvals": pending_suppliers if "supplier" in categories else [], "receipt_status": _receipt_summary(business_id) if "receipts" in categories else {"pending": 0},
                       "activity": [] if "activity" not in categories else []})
    elif role == "Manager":
        report.update({"low_stock": low if "inventory" in categories else [], "out_of_stock": out if "inventory" in categories else [], "receipt_status": _receipt_summary(business_id) if "receipts" in categories else {"pending": 0},
                       "operational_alerts": ["Review low-stock and receipt-verification items in Daily Operations."]})
    else:
        report.update({"sales": today if "sales" in categories else {"sales_total": 0, "order_count": 0}, "orders": today["order_count"] if "sales" in categories else 0})
    return report


def _receipt_summary(business_id):
    import sqlite3
    with sqlite3.connect("business_brain.db") as conn:
        row = conn.execute("SELECT COUNT(*) FROM receipt_verifications WHERE business_id=? AND status IN ('Needs Review','Possible mismatch','Unclear')", (business_id,)).fetchone()
        return {"pending": int(row[0] or 0)}


def format_daily_report(report):
    role = report["role"]
    lines = [f"Business Brain — Daily Report", f"Business: {report['business'].get('name','Business Brain')}", f"Date: {report['date']}", f"Generated for: {role}"]
    if role in ("Owner", "Admin"):
        if report.get("sales", {}).get("order_count", 0) or report.get("sales", {}).get("sales_total", 0):
            lines += ["", f"Today's Sales: {_money(report['sales']['sales_total'])}", f"Orders: {report['orders']}"]
        if "low_stock" in report:
            lines += ["", "Low Stock:"]
            lines += [f"- {p['name']} — {float(p['stock_quantity']):g} {p.get('unit') or 'unit'}" for p in report["low_stock"]] or ["- None"]
        if "missing_price" in report:
            lines += ["", f"Missing Prices: {len(report['missing_price'])}", f"Out of Stock: {len(report.get('out_of_stock', []))}"]
        if "pending_approvals" in report:
            lines += [f"Supplier/Approval Actions: {len(report['pending_approvals'])}"]
        if "receipt_status" in report:
            lines += [f"Receipt Verification Pending: {report['receipt_status']['pending']}"]
    elif role == "Manager":
        if "low_stock" in report:
            lines += ["", "Low Stock:"]
            lines += [f"- {p['name']} — {float(p['stock_quantity']):g} {p.get('unit') or 'unit'}" for p in report["low_stock"]] or ["- None"]
        if "out_of_stock" in report:
            lines += ["", f"Out of Stock: {len(report['out_of_stock'])}"]
        if "receipt_status" in report:
            lines += [f"Receipt Verification Pending: {report['receipt_status']['pending']}"]
        lines += [f"- {x}" for x in report.get("operational_alerts", [])]
    else:
        if "sales" in report:
            lines += ["", f"Today's Sales: {_money(report['sales']['sales_total'])}", f"Orders: {report['orders']}"]
    return "\n".join(lines)


def send_daily_report(role, business_id, recipient, report_date=None, include_pdf=True, categories=None):
    report = build_daily_report(role, business_id, report_date, categories)
    result = send_text(recipient, format_daily_report(report))
    document = None
    if include_pdf:
        try:
            from pdf_reports import build_daily_report_pdf
            filename = f"daily_report_{report['date']}_{str(role).lower()}.pdf"
            document = send_document(recipient, build_daily_report_pdf(role, business_id, report_date, categories), filename)
        except Exception as exc:
            # Text report remains successful even when document media is unavailable.
            document = {"error": str(exc)}
    return {"report": report, "response": result, "document": document}
