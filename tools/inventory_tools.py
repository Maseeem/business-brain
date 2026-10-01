from database import get_product_by_id


def get_stock(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    return None if not product else product["stock_quantity"]


def get_minimum_stock(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    return None if not product else product["minimum_stock"]


def check_low_stock(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    if not product:
        return None
    return {
        "product_id": product["id"],
        "name": product["name"],
        "stock": product["stock_quantity"],
        "minimum_stock": product["minimum_stock"],
        "low_stock": product["stock_quantity"] <= product["minimum_stock"],
        "unit": product["unit"],
    }
