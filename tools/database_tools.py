from database import (
    create_sale,
    create_sale_items,
    create_supplier_order,
    save_receipt_verification as db_save_receipt_verification,
)


def save_sale(transaction_ref, total, created_by=0, status="Confirmed", business_id=1):
    return create_sale(transaction_ref, total, created_by, status, business_id)


def save_sale_items(sale_id, items, business_id=1):
    return create_sale_items(sale_id, items, business_id)


def save_supplier_order(supplier_id, items, created_by=0, business_id=1):
    return create_supplier_order(supplier_id, items, created_by, business_id)


def save_supplier_order_items(*args, **kwargs):
    """Reserved compatibility wrapper; items are saved with save_supplier_order."""
    return save_supplier_order(*args, **kwargs)


def save_receipt_verification(sale_id, status, extracted_receipt, mismatches, created_by=0, business_id=1):
    return db_save_receipt_verification(sale_id, status, extracted_receipt, mismatches, created_by, business_id)
