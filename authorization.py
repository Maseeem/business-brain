"""Small backend authorization adapter for sensitive actions."""
from access_control import require


def require_action(user, permission):
    return require(user, permission)
