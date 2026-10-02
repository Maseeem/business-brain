"""Central role permissions for the Business Brain application."""

ROLE_PERMISSIONS = {
    "Owner": {
        "dashboard": True, "sales": True, "inventory": True, "receipts": True,
        "daily_operations": True, "ask_brain": True, "knowledge": True,
        "processes": True, "record_process": True, "activity": True, "suppliers": True,
        "settings": True, "users": True, "business_settings": True,
        "whatsapp": True, "reports_full": True, "supplier_approve": True,
        "inventory_edit": True, "pricing": True, "edit": True, "record": True,
    },
    "Admin": {
        "dashboard": True, "sales": True, "inventory": True, "receipts": True,
        "daily_operations": True, "ask_brain": True, "knowledge": True,
        "processes": True, "record_process": True, "activity": True, "suppliers": True,
        "settings": True, "users": True, "business_settings": True,
        "whatsapp": True, "reports_full": True, "supplier_approve": True,
        "inventory_edit": True, "pricing": True, "edit": True, "record": True,
    },
    "Manager": {
        "dashboard": False, "inventory": True, "receipts": True, "daily_operations": True,
        "ask_brain": False, "sales": False, "knowledge": False, "processes": False,
        "record_process": False, "activity": False, "suppliers": False, "settings": False,
        "users": False, "business_settings": False, "whatsapp": False,
        "reports_full": False, "supplier_approve": False, "inventory_edit": True,
        "pricing": True,
    },
    "Employee": {
        "dashboard": False, "sales": True, "inventory": False, "receipts": False,
        "daily_operations": False, "ask_brain": False, "knowledge": False,
        "processes": False, "record_process": False, "activity": False, "suppliers": False,
        "settings": False, "users": False, "business_settings": False, "whatsapp": False,
        "reports_full": False, "supplier_approve": False, "inventory_edit": False,
        "pricing": False,
    },
}


def role_of(user_or_role):
    if isinstance(user_or_role, dict):
        return str(user_or_role.get("role") or "Employee")
    return str(user_or_role or "Employee")


def can(role_or_user, permission):
    role = role_of(role_or_user)
    return bool(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["Employee"]).get(permission, False))


def require(role_or_user, permission):
    if not can(role_or_user, permission):
        raise PermissionError("You do not have permission to perform this action.")
    return True


def visible_pages(role):
    role = role_of(role)
    ordered = [
        ("Dashboard", "dashboard"), ("Smart Sale", "sales"), ("Inventory", "inventory"),
        ("Receipts", "receipts"), ("Daily Operations", "daily_operations"),
        ("Ask Brain", "ask_brain"), ("Knowledge", "knowledge"), ("Processes", "processes"),
        ("Record Process", "record_process"), ("Activity", "activity"), ("Suppliers", "suppliers"),
        ("Settings", "settings"), ("WhatsApp", "whatsapp"),
    ]
    return [label for label, perm in ordered if can(role, perm)]
