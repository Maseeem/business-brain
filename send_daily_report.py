"""Scheduler-compatible daily WhatsApp report entry point.

Run this from cron, GitHub Actions, Cloud Scheduler, or another external scheduler.
Streamlit app execution itself is not treated as a persistent background worker.
"""
import sys
from datetime import datetime

from database import init_db, get_whatsapp_settings, update_whatsapp_status
from whatsapp_service import send_daily_report


def main():
    init_db()
    business_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    settings = get_whatsapp_settings(business_id)
    if not settings.get("enabled"):
        print("WhatsApp daily reporting is disabled.")
        return 0
    recipients_by_role = settings.get("role_recipients") or {}
    sent = 0
    errors = []
    for role in ("Owner", "Manager", "Employee"):
        for recipient in recipients_by_role.get(role, []) or []:
            try:
                send_daily_report(role, business_id, recipient, categories=settings.get("categories") or None)
                sent += 1
            except Exception as exc:
                errors.append(f"{role}: {str(exc)[:250]}")
    if sent:
        update_whatsapp_status(business_id, f"Sent to {sent} recipient(s)", "; ".join(errors)[:500], datetime.now().isoformat(timespec="seconds"))
    elif errors:
        update_whatsapp_status(business_id, "Failed", "; ".join(errors)[:500], "")
    print(f"WhatsApp daily report run complete: {sent} send(s).")
    if errors:
        print("Errors: " + "; ".join(errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
