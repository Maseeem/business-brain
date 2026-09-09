# Business Brain

A startup-ready Streamlit MVP that teaches a business to AI through structured processes and business knowledge, then answers questions using grounded RAG retrieval.

## Included
- Dashboard V2 health/coverage view
- Clear SaaS-style navigation and page guidance
- AI Process Recorder → editable SOP → save → index
- Process Library V2: search, category filter, stats, detail view, edit/re-index
- Knowledge base with duplicate protection and indexing
- Ask Brain with grounded sources and exact insufficient-evidence fallback
- Activity/audit trail
- SQLite schema migration for older MVP databases
- Gemini 3.6 Flash default with current SDK-compatible generation settings

## Run locally
1. Create a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`.
4. Add `GEMINI_API_KEY`. Optionally set `GEMINI_MODEL=gemini-3.6-flash`.
5. Run: `streamlit run app.py`

## Streamlit Cloud
Add `GEMINI_API_KEY` in Secrets. If `GEMINI_MODEL` exists from an older deployment, change it to `gemini-3.6-flash` or remove it so the code default is used.

## RAG flow
Question → retrieve/rank stored chunks → provide evidence to Gemini → grounded answer → show sources.

The MVP is read-only: it does not send emails, change external business records, make financial decisions, or take external actions automatically.
