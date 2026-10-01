"""Offline smoke test for the deterministic Business Brain core.

Run with:
    python tests/smoke_test.py

It does not call Gemini, Groq or CrewAI.
"""
import os
import tempfile
from pathlib import Path

import database
from agents.receipt_agent import compare_receipt_to_order
from agents.smart_sale_agent import apply_cart_edit, build_cart


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        database.DB_PATH = Path(path)
        database.init_db()
        database.seed_demo_data()
        database.seed_operational_data()
        database.ensure_demo_users()

        user = database.authenticate_user("admin", "BusinessBrain123!")
        assert user, "Demo Owner authentication failed"

        built = build_cart("2 Pepsi aur 1 Tissue", user["business_id"])
        assert float(built["total"]) == 280.0

        edited = apply_cart_edit(built["cart"], "Tissue 3 kar do", user["business_id"])
        assert float(edited["total"]) == 440.0

        sale_id = database.save_confirmed_sale(
            "SMOKE-001", edited["total"], edited["cart"], user["id"], user["business_id"]
        )
        sale = database.get_sale(sale_id, user["business_id"])
        assert sale and len(sale["items"]) == 2
        assert sale["total"] == 440.0

        try:
            database.save_confirmed_sale(
                "SMOKE-002", 99999, edited["cart"], user["id"], user["business_id"]
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Tampered sale total was not rejected")

        comparison = compare_receipt_to_order(
            {"items": [{"name": "Pepsi", "quantity": 1, "unit_price": 100}], "total": 100},
            [{"product_id": 1, "name": "Pepsi", "quantity": 1, "unit_price": 100}],
            100,
        )
        assert comparison["status"] == "Match"
        print("Business Brain deterministic smoke test: PASS")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
