# Business Brain

Business Brain is a polished Streamlit MVP for turning scattered business knowledge into an organized, searchable AI knowledge system.

> **Capture → Understand → Structure → Remember → Retrieve → Assist**

The product is deliberately more than “upload a PDF and chat with it.” The Process Recorder and Business Brain share the same knowledge layer:

**Record Process → AI structures SOP → Human reviews → Save/index → Business Brain retrieves → Grounded answer + sources**

## MVP features

- Professional SaaS-style dashboard
- Demo workspace for **Nova Bakery**
- AI Process Recorder
- Editable AI-generated SOPs
- Business Knowledge Base
- PDF, DOCX, TXT/MD, CSV, XLSX and image ingestion
- Local TF-IDF retrieval layer for a dependency-light prototype
- Gemini Flash generation
- Grounded Business Brain answers with source evidence
- Process Library
- Process detail pages
- Activity log
- SQLite persistence
- Missing-key and upload/error handling
- Architecture designed so retrieval can later move to a hosted vector database

## Project structure

```text
business_brain/
├── app.py
├── agent.py
├── rag.py
├── database.py
├── ui.py
├── requirements.txt
├── .env.example
├── README.md
└── business_brain.db        # created automatically at runtime
```

### Responsibilities

- `app.py` — Streamlit pages, interaction flow and orchestration
- `ui.py` — reusable visual components and SaaS styling
- `database.py` — SQLite persistence, demo data, activity log
- `rag.py` — file extraction, chunking, indexing and retrieval
- `agent.py` — Gemini integration, SOP generation and grounded Q&A

## Setup

### 1. Create an environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Gemini

Copy `.env.example` to `.env`:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Keep `.env` private and never commit it to GitHub.

### 4. Run

```bash
streamlit run app.py
```

The app creates `business_brain.db` automatically and seeds Nova Bakery demo data on first launch.

## Demo flow

1. Open **Record Process**
2. Describe a process such as “New Customer Order”
3. Optionally attach supporting evidence
4. Click **Generate SOP**
5. Review/edit the generated SOP
6. Click **Save to Business Brain**
7. Open **Ask Brain**
8. Ask:
   - “How does our order process work?”
   - “What information is required before creating an order?”
   - “What should I do after receiving an order?”
9. Inspect the source evidence shown below the answer.

The demo data already contains:
- New Customer Order
- Custom Cake Order
- Inventory Restocking
- Customer Complaint Handling
- Customer Service Policy
- Pricing Guide
- Order Requirements
- Refund Policy

## RAG architecture

```text
User question
     │
     ▼
Query
     │
     ▼
Local retrieval layer
(TF-IDF + word/bigram similarity)
     │
     ▼
Top relevant chunks
     │
     ▼
Grounded prompt
     │
     ▼
Gemini Flash
     │
     ▼
Answer + source evidence
```

### Why TF-IDF for the MVP?

It keeps the prototype simple, local and easy to run without an external vector database or infrastructure account. It also preserves a clean `retrieve()` interface.

For production, replace the implementation behind `rag.retrieve()` with:

- pgvector/Postgres
- Qdrant
- Pinecone
- Weaviate
- another managed/vector-native store

The generation layer does not need to change.

## Grounding behavior

Business Brain is explicitly instructed to use retrieved business context only.

If retrieval finds nothing useful, the application returns:

> I couldn't find enough information in your Business Brain to answer this confidently.

The assistant is read-only in the MVP. It does not send email, change records, make financial decisions or execute external actions.

## Process Recorder architecture

The recorder accepts:

- plain-language descriptions
- PDFs
- DOCX/TXT/MD/CSV/XLSX evidence
- screenshots/images

Gemini converts the evidence into a structured SOP schema:

- process name
- category
- purpose
- trigger
- required inputs
- roles
- steps
- decisions
- exceptions
- output
- tags

The user reviews the draft before saving. The saved process is then converted into a canonical searchable representation and indexed alongside knowledge documents.

## Startup roadmap

### Phase 1 — MVP
- Single workspace
- Process Recorder
- Knowledge Base
- Grounded Business Brain
- Process library
- Local retrieval

### Phase 2 — Team product
- Authentication
- Multi-business tenancy
- Multiple users
- Role-based permissions
- Process ownership
- Version history
- Audit logs

### Phase 3 — Strong knowledge infrastructure
- Postgres + pgvector
- Hybrid keyword/vector retrieval
- Reranking
- Better document parsing
- Knowledge relationships
- source-level permissions

### Phase 4 — Business agent
- Approved tools
- Human confirmation
- Integrations
- Workflow suggestions
- Analytics
- automation

## Production hardening checklist

Before production deployment, add:

- authentication and authorization
- tenant isolation
- encrypted secrets
- managed Postgres
- object storage for uploaded files
- async ingestion jobs
- document-level permissions
- rate limiting
- observability and tracing
- prompt/version management
- evaluation datasets for RAG quality
- backups and migrations
- malware/file validation
- PII and retention controls

## Design principle

The core product idea is not “chat with documents.”

It is:

> **Teach your business to AI, and build a Business Brain that remembers how your company works.**
