from database import find_supplier, find_supplier_for_product, create_supplier_order


def find_supplier_tool(name, business_id=1):
    return find_supplier(name, business_id)


def find_supplier_for_product_tool(product_id, business_id=1):
    return find_supplier_for_product(product_id, business_id)


def create_supplier_order_draft(supplier_id, items, created_by=0, business_id=1):
    if not items:
        raise ValueError("Supplier order must contain at least one item.")
    return create_supplier_order(supplier_id, items, created_by, business_id)
