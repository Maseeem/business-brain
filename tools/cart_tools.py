from decimal import Decimal


def create_cart():
    return []


def add_item(cart, product, quantity):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    for item in cart:
        if item["product_id"] == product["id"]:
            item["quantity"] = float(Decimal(str(item["quantity"])) + quantity)
            item["subtotal"] = calculate_subtotal(item["quantity"], item["unit_price"])
            return cart
    cart.append({
        "product_id": product["id"],
        "name": product["name"],
        "quantity": float(quantity),
        "unit_price": float(product["price"]),
        "subtotal": calculate_subtotal(quantity, product["price"]),
        "unit": product.get("unit", "unit"),
    })
    return cart


def remove_item(cart, product_id):
    return [item for item in cart if item["product_id"] != product_id]


def change_quantity(cart, product_id, quantity):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    for item in cart:
        if item["product_id"] == product_id:
            item["quantity"] = float(quantity)
            item["subtotal"] = calculate_subtotal(quantity, item["unit_price"])
            return cart
    raise ValueError("Product is not in the current cart.")


def calculate_subtotal(quantity, unit_price):
    return float(Decimal(str(quantity)) * Decimal(str(unit_price)))


def calculate_total(cart):
    return round(sum(Decimal(str(item["subtotal"])) for item in cart), 2)
