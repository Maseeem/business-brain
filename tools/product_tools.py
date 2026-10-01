from database import find_product, get_product_by_id


def find_product_tool(query, business_id=1):
    return find_product(query, business_id)


def find_product_alias(query, business_id=1):
    return find_product(query, business_id)


def get_price(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    return None if not product else product["price"]


def get_stock(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    return None if not product else product["stock_quantity"]


def get_minimum_stock(product_id, business_id=1):
    product = get_product_by_id(product_id, business_id)
    return None if not product else product["minimum_stock"]
