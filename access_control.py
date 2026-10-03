"""Central role permissions for Business Brain.

One permission matrix is shared by navigation and server-side guards.
"""
ROLE_PERMISSIONS = {
    "Owner": {
        "dashboard": True, "sales": True, "inventory": True, "receipts": True, "daily_operations": True,
        "ask_brain": True, "knowledge": True, "processes": True, "record_process": True, "activity": True,
        "suppliers": True, "settings": True, "users": True, "business_settings": True, "whatsapp": True,
        "whatsapp_admin": True, "reports_full": True, "supplier_approve": True, "inventory_edit": True, "inventory_remove": True,
        "pricing": True, "edit": True, "record": True, "process_read": True, "ask_brain_read": True,
    },
    "Admin": {
        "dashboard": True, "sales": True, "inventory": True, "receipts": True, "daily_operations": True,
        "ask_brain": True, "knowledge": True, "processes": True, "record_process": True, "activity": True,
        "suppliers": True, "settings": True, "users": True, "business_settings": True, "whatsapp": True,
        "whatsapp_admin": True, "reports_full": True, "supplier_approve": True, "inventory_edit": True, "inventory_remove": True,
        "pricing": True, "edit": True, "record": True, "process_read": True, "ask_brain_read": True,
    },
    "Manager": {
        "dashboard": True, "sales": False, "inventory": True, "receipts": True, "daily_operations": True,
        "ask_brain": True, "knowledge": False, "processes": True, "record_process": False, "activity": False,
        "suppliers": False, "settings": False, "users": False, "business_settings": False, "whatsapp": True,
        "whatsapp_admin": False, "reports_full": False, "supplier_approve": False, "inventory_edit": True, "inventory_remove": True,
        "pricing": True, "edit": False, "record": False, "process_read": True, "ask_brain_read": True,
    },
    "Employee": {
        "dashboard": True, "sales": True, "inventory": False, "receipts": True, "daily_operations": False,
        "ask_brain": True, "knowledge": False, "processes": True, "record_process": False, "activity": False,
        "suppliers": False, "settings": False, "users": False, "business_settings": False, "whatsapp": True,
        "whatsapp_admin": False, "reports_full": False, "supplier_approve": False, "inventory_edit": False, "inventory_remove": False,
        "pricing": False, "edit": False, "record": False, "process_read": True, "ask_brain_read": True,
    },
}

def role_of(user_or_role):
    if isinstance(user_or_role, dict): return str(user_or_role.get("role") or "Employee")
    return str(user_or_role or "Employee")

def can(role_or_user, permission):
    role=role_of(role_or_user)
    return bool(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["Employee"]).get(permission, False))

def require(role_or_user, permission):
    if not can(role_or_user, permission):
        raise PermissionError("You do not have permission to perform this action.")
    return True

def visible_pages(role):
    ordered=[
        ("Dashboard","dashboard"),("Smart Sale","sales"),("Inventory","inventory"),("Receipts","receipts"),
        ("Daily Operations","daily_operations"),("Ask Brain","ask_brain"),("Knowledge","knowledge"),("Processes","processes"),
        ("Record Process","record_process"),("Activity","activity"),("Suppliers","suppliers"),("Settings","settings"),("WhatsApp","whatsapp"),
    ]
    return [label for label,perm in ordered if can(role,perm)]
