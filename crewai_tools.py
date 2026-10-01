"""Small CrewAI tools used by specialized agents.

The tools only read business data. Financial writes and stock changes remain
behind deterministic database functions so the LLM cannot directly mutate data.
"""

try:
    from crewai.tools import tool
except Exception:  # pragma: no cover - keeps imports resilient during local setup
    tool = None


def get_product_tools():
    if tool is None:
        return []

    @tool("lookup_product_catalog")
    def lookup_product_catalog(business_id: int) -> str:
        """Return the active product catalogue for a business as JSON."""
        import json
        from database import list_products
        products = [
            {"id": p["id"], "name": p["name"], "aliases": p.get("aliases", ""), "unit": p.get("unit", "unit")}
            for p in list_products(int(business_id))
        ]
        return json.dumps(products, ensure_ascii=False)

    return [lookup_product_catalog]


def get_inventory_tools():
    if tool is None:
        return []

    @tool("read_inventory_snapshot")
    def read_inventory_snapshot(business_id: int) -> str:
        """Return current stock and minimum-stock levels as JSON."""
        import json
        from database import list_products
        rows = [
            {"id": p["id"], "name": p["name"], "stock": p["stock_quantity"], "minimum_stock": p["minimum_stock"], "unit": p["unit"]}
            for p in list_products(int(business_id))
        ]
        return json.dumps(rows, ensure_ascii=False)

    return [read_inventory_snapshot]
