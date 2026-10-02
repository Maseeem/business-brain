"""Professional PDF receipts and deterministic role-scoped daily reports.

ReportLab is the only PDF *generation* library used by this feature. The existing
pypdf dependency remains solely for the pre-existing RAG document ingestion path.
"""
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from database import get_business, get_daily_operations, list_products, query_today_sales, list_supplier_orders
from whatsapp_service import build_daily_report


def _money(value):
    return f"Rs. {float(value or 0):,.2f}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReceiptTitle", parent=base["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#155c3b"), spaceAfter=5),
        "heading": ParagraphStyle("ReceiptHeading", parent=base["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#155c3b"), spaceBefore=9, spaceAfter=5),
        "body": ParagraphStyle("ReceiptBody", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#34443a")),
        "small": ParagraphStyle("ReceiptSmall", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=colors.HexColor("#66736b")),
    }


def _table(data, widths=None, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#dfe9e3")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eef8f2")), ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#34443a")), ("FONTSIZE", (0,0), (-1,-1), 7.5), ("BOTTOMPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5)]
    if not header:
        commands = commands[0:2] + commands[2:]
    t.setStyle(TableStyle(commands))
    return t


def build_sale_receipt_pdf(sale, business, user):
    styles = _styles(); buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=14*mm, bottomMargin=14*mm)
    story = [Paragraph(str(business.get("name") or "Business Brain"), styles["title"])]
    if business.get("profile"):
        story.append(Paragraph(str(business["profile"]), styles["small"]))
    story += [Spacer(1, 6), Paragraph("SALE RECEIPT", styles["heading"])]
    meta = [["Transaction", str(sale.get("transaction_ref", "")), "Sale ID", f"#{sale.get('id','')}"], ["Date / Time", str(sale.get("created_at", "")), "Cashier", str(user.get("name", ""))], ["Role", str(user.get("role", "")), "", ""]]
    if sale.get("customer_name"):
        meta.append(["Customer", str(sale.get("customer_name")), "", ""])
    story.append(_table(meta, [28*mm, 63*mm, 25*mm, 54*mm], header=False))
    story.append(Spacer(1, 8))
    rows = [["Product", "Qty", "Unit", "Unit Price", "Subtotal"]]
    for item in sale.get("items", []):
        rows.append([str(item.get("name", "Product")), f"{float(item.get('quantity',0)):g}", str(item.get("unit") or "unit"), _money(item.get("unit_price")), _money(item.get("subtotal"))])
    story.append(_table(rows, [65*mm, 18*mm, 18*mm, 35*mm, 35*mm]))
    story += [Spacer(1, 8), Paragraph(f"Subtotal: {_money(sum(float(x.get('subtotal',0) or 0) for x in sale.get('items', [])))}", styles["body"]), Paragraph(f"Total: {_money(sale.get('total'))}", ParagraphStyle("Total", parent=styles["body"], fontSize=12, leading=15, textColor=colors.HexColor("#155c3b"), spaceBefore=3)), Spacer(1, 18), Paragraph("Thank you for your business.", styles["body"])]
    doc.build(story); return buf.getvalue()


def build_daily_report_pdf(role, business_id, report_date=None, categories=None):
    report = build_daily_report(role, business_id, report_date, categories); business = report["business"]; styles = _styles(); buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=14*mm, bottomMargin=14*mm)
    story = [Paragraph("Business Brain — Daily Report", styles["title"]), Paragraph(f"Business: {business.get('name','Business Brain')}", styles["body"]), Paragraph(f"Report Date: {report['date']} · Generated: {report['generated_at']} · Generated For: {role}", styles["small"])]
    if role in ("Owner", "Admin"):
        story.append(Paragraph("1. Sales Summary", styles["heading"])); story.append(_table([["Metric","Value"],["Today's Sales",_money(report['sales']['sales_total'])],["Today's Orders",str(report['orders'])]], [70*mm, 80*mm]))
        story.append(Paragraph("2. Inventory / Low Stock", styles["heading"])); story.append(_inventory_table(report["low_stock"], report["inventory"]))
        story.append(Paragraph("3. Missing Prices", styles["heading"])); story.append(Paragraph(", ".join(p["name"] for p in report["missing_price"]) or "None", styles["body"]))
        story.append(Paragraph("4. Supplier / Reorder Actions", styles["heading"])); story.append(Paragraph("; ".join(f"Order #{o['id']} · {o['supplier_name']} · {o['status']}" for o in report["pending_approvals"]) or "No pending supplier approvals.", styles["body"]))
        story.append(Paragraph("5. Receipt / Verification Summary", styles["heading"])); story.append(Paragraph(f"Pending verification: {report['receipt_status']['pending']}", styles["body"]))
    elif role == "Manager":
        story.append(Paragraph("1. Sales / Order Summary", styles["heading"])); story.append(_table([["Metric","Value"],["Today's Sales",_money(report['sales']['sales_total'])],["Today's Orders",str(report['orders'])]], [70*mm, 80*mm]))
        story.append(Paragraph("2. Inventory / Low Stock", styles["heading"])); story.append(_inventory_table(report["low_stock"], report["low_stock"]))
        story.append(Paragraph("3. Supplier / Order Status", styles["heading"])); story.append(Paragraph("; ".join(f"Order #{o['id']} · {o['supplier_name']} · {o['status']}" for o in report.get("supplier_orders", [])) or "No supplier orders.", styles["body"]))
        story.append(Paragraph("4. Receipt / Verification", styles["heading"])); story.append(Paragraph(f"Pending verification: {report['receipt_status']['pending']}", styles["body"]))
        story.append(Paragraph("5. Operational Alerts", styles["heading"])); story.append(Paragraph("\n".join(report["operational_alerts"]), styles["body"]))
    else:
        story.append(Paragraph("1. Sales Summary", styles["heading"])); story.append(_table([["Metric","Value"],["Today's Sales",_money(report['sales']['sales_total'])],["Today's Orders",str(report['orders'])]], [70*mm, 80*mm]))
    story += [Spacer(1, 14), Paragraph("Business Brain — role-scoped report", styles["small"])]
    doc.build(story); return buf.getvalue()


def _inventory_table(items, full_inventory):
    if not items:
        return Paragraph("No low-stock products.", _styles()["body"])
    rows = [["Product", "Stock", "Unit", "Minimum"]]
    for p in items:
        rows.append([str(p.get("name")), f"{float(p.get('stock_quantity',0) or 0):g}", str(p.get("unit") or "unit"), f"{float(p.get('minimum_stock',0) or 0):g}"])
    return _table(rows, [70*mm, 25*mm, 25*mm, 30*mm])
