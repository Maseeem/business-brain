# Business Brain — Recovered Complete Project

This version restores the original Business Brain knowledge/process workspace and combines it with the newer multi-agent shop operations workflows.

## Restored original workspace
- Dashboard
- Record Process
- Knowledge
- Ask Brain
- Processes
- Process Detail + version history
- Activity / records
- Settings + users/roles
- Original demo processes: New Customer Order, Custom Cake Order, Inventory Restocking, Customer Complaint Handling

## Operational workspace
- Smart Sale: voice/text order capture, product matching, price/stock validation, deterministic totals, confirmation, saved sale receipt
- Inventory: product search, price/stock/unit/minimum-stock editing, add products
- Daily Operations: today sales, low stock, pending supplier actions, recent sales
- Receipts: saved sale receipts, download, Gemini receipt verification + deterministic comparison
- Suppliers: low-stock reorder drafts and approval flow

## Architecture
Coordinator → Smart Sale / Receipt / Knowledge / Operations agents.
SQLite is used for persistent business data. RAG is used for business knowledge/process retrieval. Python/database logic handles prices, stock, totals, validation and writes.

## UI
Light background, green accents, readable white cards, no black-heavy interface.

## Demo data
Demo seeding is controlled by `SEED_DEMO_DATA`. Set it to `false` for a production database after the first setup.
