# Business Brain

Simple multi-agent AI operations assistant for small shops. This upload is intentionally folder-free for easy GitHub web upload.

## Main agents
- Coordinator Agent: routes sale, receipt, operations and knowledge requests.
- Smart Sale Agent: understands voice/text orders and builds a database-priced cart.
- Receipt Agent: Gemini vision extraction + deterministic Python comparison.
- Operations Agent: inventory, low-stock and supplier draft workflows.
- Knowledge Agent: answers from the existing Business Brain RAG/knowledge base.

## Shop catalog
Use **Inventory** to paste product names one per line. Products are added to the current shop. Set selling prices, units, stock and minimum stock from the same page.

## Memory
Short-term workflow memory lives in the Streamlit session. Persistent business memory is stored in SQLite. Embeddings/RAG are for knowledge documents/processes, not current prices or stock.

## Environment
Set `GROQ_API_KEY` for CrewAI/Groq agent calls and `GEMINI_API_KEY` for Gemini receipt/voice/knowledge features. Optional: `GEMINI_MODEL` and `GROQ_MODEL`.

## GitHub / Streamlit Cloud
Upload all extracted files from this ZIP into the repository root. There are no required folders. Main file: `app.py`.
