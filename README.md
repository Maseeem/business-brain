# Business Brain — Multi-Agent AI Small Shop Operations Assistant

Business Brain combines the existing Knowledge Base/RAG and SOP system with a practical multi-agent operations layer for sales, receipts, inventory and suppliers.

## Architecture

```text
User
  ↓
Coordinator Agent (CrewAI + Groq)
  ├── Smart Sale Agent → Product/Cart tools → SQLite
  ├── Receipt Agent → Gemini Vision → deterministic Python comparison
  ├── Operations Agent → Inventory/Supplier tools → SQLite
  └── Knowledge Agent → existing Business Brain RAG
```

AI handles routing, natural-language extraction and explanation. Python/SQLite handles prices, arithmetic, validation, stock, records and approvals.

## Features

- Existing Knowledge Base/RAG and SOP workflows
- Owner / Manager / Employee roles
- Smart Sale with voice or text order input
- Database-backed prices and deterministic totals
- Atomic sale + inventory transaction
- Receipt extraction with Gemini and deterministic comparison
- Low-stock monitoring and supplier-order drafts
- Owner/Manager approval for supplier orders
- Daily Operations page
- Premium dark responsive Streamlit UI

## Demo accounts

With `SEED_DEMO_DATA=true`:

- `admin` / `BusinessBrain123!` — Owner
- `manager` / `BusinessBrain123!` — Manager
- `employee` / `BusinessBrain123!` — Employee

Use `SEED_DEMO_DATA=false` for production. Change demo passwords before real use.

## Local setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Create `.env` from `.env.example` and configure `GEMINI_API_KEY`, `GROQ_API_KEY`, and optional model variables. Never commit `.env` or API keys.

## GitHub browser upload

1. Create a GitHub repository.
2. Choose **Add file → Upload files**.
3. Upload the project folders and files while preserving their folder structure.
4. Commit the upload.
5. For later edits, open a file on GitHub, edit it, and commit the change.

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

Environment variables:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
SEED_DEMO_DATA=false
```

## Project structure

```text
business-brain-main/
├── app.py
├── database.py
├── agent.py
├── rag.py
├── ui.py
├── agents/
│   ├── coordinator_agent.py
│   ├── smart_sale_agent.py
│   ├── receipt_agent.py
│   ├── operations_agent.py
│   ├── knowledge_agent.py
│   └── runtime.py
├── tools/
│   ├── product_tools.py
│   ├── cart_tools.py
│   ├── inventory_tools.py
│   ├── supplier_tools.py
│   └── database_tools.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Demo flows

**Smart Sale:** `1 Pepsi, 2 tissue aur 1 Surf` → Coordinator → Smart Sale Agent → database prices → Python total → confirmation → atomic sale/stock update.

**Receipt:** upload a saved-sale receipt → Gemini extracts visible values → Python compares the extracted values with the saved order.

**Operations:** Daily Operations → low stock → supplier draft → Owner/Manager approval.

**Knowledge:** ask a policy/process question → existing RAG → evidence-backed answer.

## Limitations

SQLite is intentionally used for a simple deployable project. Voice and receipt features depend on API availability and image/audio clarity. Supplier orders are drafts until a permitted user approves them.
