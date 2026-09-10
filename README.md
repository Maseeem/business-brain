# Business Brain — Phase 2

This version keeps the working Business Brain MVP and adds three requested capabilities:

1. **Employee Login + Multi-Role Permissions**
   - Owner: full access
   - Manager: can record processes, add knowledge, edit SOPs
   - Employee: view/ask only
   - Passwords are stored as PBKDF2 hashes in SQLite.

2. **Smart SOP Versioning + Audit Trail**
   - Every saved SOP gets a version number.
   - Editing creates a new version instead of overwriting history.
   - Previous versions can be reviewed and restored; restoring creates a new version.
   - Activity records include the acting user.

3. **Voice-to-SOP**
   - Record a process with Streamlit's microphone input.
   - Gemini 3.6 Flash transcribes the recording.
   - The transcript is converted into the same editable SOP workflow.
   - This is a reliable MVP recording flow, not continuous live word-by-word transcription.

## Demo accounts

For testing only:

- `admin` / `BusinessBrain123!` — Owner
- `manager` / `BusinessBrain123!` — Manager
- `employee` / `BusinessBrain123!` — Employee

Change these before production use.

## Run locally

```bash
pip install -r requirements.txt
```

Set `GEMINI_API_KEY` in `.env` or Streamlit Secrets. `GEMINI_MODEL` is optional and defaults to `gemini-3.6-flash`.

```bash
streamlit run app.py
```

## Streamlit Cloud

Upload these files to the same GitHub repository:

- `app.py`
- `database.py`
- `agent.py`
- `rag.py`
- `ui.py`
- `requirements.txt`

In Streamlit Secrets, keep:

```toml
GEMINI_API_KEY = "your-key"
```

If you have an old `GEMINI_MODEL`, use:

```toml
GEMINI_MODEL = "gemini-3.6-flash"
```

## Important production note

The login system is appropriate for this MVP/demo. Before a real public SaaS launch, replace the demo SQLite authentication with a production identity provider, secure password-reset flow, session hardening, account lockout/rate limiting, and proper multi-tenant authorization.
