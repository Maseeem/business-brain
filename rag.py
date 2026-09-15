import io
import json
import re
from pathlib import Path
from difflib import get_close_matches

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import (
    create_knowledge,
    add_chunk,
    clear_chunks_for,
    list_chunks,
    list_knowledge,
    log_activity,
)

SUPPORTED = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx",
    ".png", ".jpg", ".jpeg", ".webp",
}


def _normalize_for_duplicate(value):
    """Normalize text so harmless spacing/case differences do not create duplicates."""
    value = value or ""
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def _is_duplicate_knowledge(title, content):
    """
    Return True only when both the normalized title and normalized content
    already exist in the Business Brain.

    Same title + different content is allowed.
    Same content + different title is also allowed.
    """
    normalized_title = _normalize_for_duplicate(title)
    normalized_content = _normalize_for_duplicate(content)

    if not normalized_title or not normalized_content:
        return False

    for item in list_knowledge():
        if (
            _normalize_for_duplicate(item.get("title", "")) == normalized_title
            and _normalize_for_duplicate(item.get("content", "")) == normalized_content
        ):
            return True

    return False


def _extract_text_from_upload(uploaded_file):
    """Extract text from supported document uploads."""
    if not uploaded_file:
        return ""

    ext = Path(uploaded_file.name).suffix.lower()
    data = uploaded_file.getvalue()

    if ext in {".txt", ".md", ".csv"}:
        return data.decode("utf-8", errors="ignore")

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]

        for table in doc.tables:
            for row in table.rows:
                vals = [
                    cell.text.strip()
                    for cell in row.cells
                    if cell.text.strip()
                ]
                if vals:
                    parts.append(" | ".join(vals))

        return "\n".join(parts)

    if ext == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(
            io.BytesIO(data),
            data_only=True,
        )

        parts = []

        for ws in wb.worksheets:
            parts.append(f"Sheet: {ws.title}")

            for row in ws.iter_rows(values_only=True):
                vals = [
                    str(v).strip()
                    for v in row
                    if v is not None and str(v).strip()
                ]

                if vals:
                    parts.append(" | ".join(vals))

        return "\n".join(parts)

    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return ""

    raise ValueError(f"Unsupported file type: {ext}")


def _chunk(text, size=1200, overlap=180):
    """Split text into overlapping chunks and always advance safely."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        return []

    size = max(int(size), 100)
    overlap = max(0, min(int(overlap), size - 1))

    chunks = []
    start = 0

    while start < len(text):
        end = min(len(text), start + size)
        piece = text[start:end]

        if end < len(text):
            cut = max(
                piece.rfind("\n\n"),
                piece.rfind(". "),
                piece.rfind(" "),
            )

            if cut > size * 0.55:
                end = start + cut + 1
                piece = text[start:end]

        piece = piece.strip()

        if len(piece) > 30:
            chunks.append(piece)

        next_start = end - overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    return [x.strip() for x in text.splitlines() if x.strip()] if text else []


def _step_text(value):
    if isinstance(value, dict):
        return str(value.get("action", "")).strip()
    return str(value).strip()


def _process_chunks(process):
    """Create semantically focused chunks so role/title questions hit the right evidence."""
    name = str(process.get("name", "Untitled Process"))
    category = str(process.get("category", ""))
    purpose = str(process.get("description", ""))
    trigger = str(process.get("trigger", ""))
    def field_list(name):
        value = process.get(name)
        if value:
            return _as_list(value)
        raw = process.get(name + "_json")
        if raw:
            try:
                return _as_list(json.loads(raw))
            except Exception:
                return []
        return []

    inputs = field_list("inputs")
    roles = field_list("roles")
    raw_steps = process.get("steps")
    if not raw_steps and process.get("steps_json"):
        try:
            raw_steps = json.loads(process.get("steps_json"))
        except Exception:
            raw_steps = []
    steps = [_step_text(x) for x in (raw_steps or []) if _step_text(x)]
    decisions = field_list("decisions")
    exceptions = field_list("exceptions")
    tags = field_list("tags")
    output = str(process.get("output", ""))

    overview = f"""Process: {name}
Category: {category}
Purpose: {purpose}
Trigger: {trigger}
People / Roles involved: {', '.join(roles)}
Responsibilities: {', '.join(roles)}
Required inputs: {', '.join(inputs)}
Expected output: {output}
Tags: {', '.join(tags)}""".strip()

    workflow = f"Process: {name}\nWorkflow / Steps:\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(steps))
    decisions_text = f"Process: {name}\nDecision points:\n" + ("\n".join(f"- {x}" for x in decisions) or "Not specified")
    exceptions_text = f"Process: {name}\nExceptions and warnings:\n" + ("\n".join(f"- {x}" for x in exceptions) or "Not specified")
    return [x for x in [overview, workflow, decisions_text, exceptions_text] if len(x.strip()) > 30]


def index_process(process_id, process):
    """Index a process into focused evidence chunks, including a dedicated roles section."""
    clear_chunks_for("process", process_id)
    pieces = _process_chunks(process)
    for i, piece in enumerate(pieces, 1):
        add_chunk(
            "process", process_id,
            process.get("name", "Untitled Process"),
            piece,
            {"chunk": i, "category": process.get("category", "Operations")},
        )
    log_activity("Process indexed", process.get("name", "Untitled Process"))


def ingest_text_knowledge(title, kind, tags, text):
    """Create and index a knowledge item from manually entered text."""
    try:
        cleaned = (text or "").strip()

        if not cleaned:
            return {
                "ok": False,
                "error": "Please provide some knowledge text.",
            }

        title = (title or "").strip() or "Untitled knowledge"
        kind = (kind or "Note").strip() or "Note"
        tag_list = [
            x.strip()
            for x in (tags or "").split(",")
            if x.strip()
        ]

        # Prevent the exact same knowledge item from being stored twice.
        if _is_duplicate_knowledge(title, cleaned):
            return {
                "ok": True,
                "duplicate": True,
                "message": "This knowledge item already exists.",
            }

        kid = create_knowledge(
            title,
            kind,
            cleaned[:220],
            "Manual note",
            tag_list,
            cleaned,
        )

        clear_chunks_for("knowledge", kid)

        for i, piece in enumerate(_chunk(cleaned), 1):
            add_chunk(
                "knowledge",
                kid,
                title,
                piece,
                {
                    "chunk": i,
                    "type": kind,
                    "source": "Manual note",
                },
            )

        log_activity("Knowledge added", title)

        return {
            "ok": True,
            "duplicate": False,
            "id": kid,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Could not index this knowledge item: {e}",
        }


def ingest_knowledge_file(
    title,
    kind,
    tags,
    uploaded_file=None,
    text="",
):
    """Create and index knowledge from typed text or an uploaded file."""
    try:
        title = (title or "").strip() or "Untitled knowledge"
        kind = (kind or "Note").strip() or "Note"
        source = (
            uploaded_file.name
            if uploaded_file
            else "Manual note"
        )

        extracted = (text or "").strip()

        if uploaded_file:
            ext = Path(uploaded_file.name).suffix.lower()
            extracted = _extract_text_from_upload(uploaded_file).strip()

            if ext in {".png", ".jpg", ".jpeg", ".webp"}:
                from agent import analyze_image_for_knowledge

                extracted = analyze_image_for_knowledge(
                    uploaded_file
                ).strip()

        if not extracted:
            return {
                "ok": False,
                "error": "The source did not contain readable content.",
            }

        # Prevent the same title + content from being added again.
        # A different title or changed content is still allowed.
        if _is_duplicate_knowledge(title, extracted):
            return {
                "ok": True,
                "duplicate": True,
                "message": "This knowledge item already exists.",
            }

        tag_list = [
            x.strip()
            for x in (tags or "").split(",")
            if x.strip()
        ]

        kid = create_knowledge(
            title,
            kind,
            extracted[:220],
            source,
            tag_list,
            extracted,
        )

        clear_chunks_for("knowledge", kid)

        for i, piece in enumerate(_chunk(extracted), 1):
            add_chunk(
                "knowledge",
                kid,
                title,
                piece,
                {
                    "chunk": i,
                    "type": kind,
                    "source": source,
                },
            )

        log_activity("Knowledge added", title)

        return {
            "ok": True,
            "duplicate": False,
            "id": kid,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Could not index this knowledge item: {e}",
        }


ROLE_TERMS = {
    "role", "roles", "people", "person", "team", "teams", "staff",
    "responsible", "responsibility", "responsibilities", "handles", "handle",
    "involved", "who", "owner", "department", "sales", "production",
    "counter", "personnel"
}

ROLE_EXPANSIONS = {
    "role": ["roles", "people", "team", "responsibility", "responsibilities", "who", "handles"],
    "roles": ["role", "people", "team", "responsibility", "responsibilities", "who", "handles"],
    "people": ["roles", "team", "staff", "personnel", "responsibility"],
    "responsible": ["responsibility", "roles", "people", "team", "handles", "owner"],
    "responsibility": ["responsibilities", "roles", "people", "team", "handles"],
    "handles": ["handle", "responsible", "responsibility", "roles", "people", "team"],
    "handle": ["handles", "responsible", "responsibility", "roles", "people", "team"],
    "involved": ["people", "roles", "team", "responsibility"],
    "team": ["teams", "roles", "people", "staff", "responsibility"],
    "teams": ["team", "roles", "people", "staff", "responsibility"],
}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").casefold())


def _expand_query(query):
    """Expand natural-language business queries without inventing facts."""
    original = (query or "").strip()
    tokens = _tokenize(original)
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(ROLE_EXPANSIONS.get(token, []))
    # Preserve the exact query and its expanded terms for TF-IDF.
    return original + " " + " ".join(expanded)


def _find_process_title_tokens(query, rows):
    """Identify stored process-title terms explicitly mentioned by the user."""
    q_tokens = set(_tokenize(query))
    title_tokens = {}
    for row in rows:
        if row.get("source_type") != "process":
            continue
        title = str(row.get("title", ""))
        meaningful = [t for t in _tokenize(title) if len(t) >= 3]
        title_tokens[row.get("source_id")] = set(meaningful)
    return q_tokens, title_tokens


def retrieve(query, top_k=6):
    """Hybrid retrieval with role-aware expansion, title boosts and grounded relevance gates."""
    query = (query or "").strip()
    if not query:
        return []

    rows = list_chunks()
    if not rows:
        return []
    corpus = [r.get("content", "") for r in rows]
    if not any(corpus):
        return []

    expanded_query = _expand_query(query)
    word_vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), sublinear_tf=True,
        max_features=16000,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
        max_features=20000,
    )
    try:
        word_matrix = word_vectorizer.fit_transform(corpus + [expanded_query])
        char_matrix = char_vectorizer.fit_transform(corpus + [query])
        word_scores = cosine_similarity(word_matrix[-1], word_matrix[:-1]).flatten()
        char_scores = cosine_similarity(char_matrix[-1], char_matrix[:-1]).flatten()
    except ValueError:
        return []

    q_tokens, title_tokens = _find_process_title_tokens(query, rows)
    role_query = bool(q_tokens & ROLE_TERMS)
    scored = []

    for idx, row in enumerate(rows):
        score = 0.60 * float(word_scores[idx]) + 0.40 * float(char_scores[idx])
        content_tokens = set(_tokenize(row.get("content", "")))
        title = str(row.get("title", ""))
        title_token_set = set(_tokenize(title))
        title_overlap = len(q_tokens & title_token_set)

        # Strong boost when the user explicitly names a stored process.
        if row.get("source_type") == "process" and title_overlap:
            score += min(0.22, 0.11 * title_overlap)

        # Role questions should favor chunks that explicitly contain the roles section.
        if role_query and row.get("source_type") == "process":
            if "roles" in content_tokens or "people" in content_tokens or "responsibilities" in content_tokens:
                score += 0.12
            if title_overlap:
                score += 0.08

        scored.append((score, idx))

    scored.sort(reverse=True)
    # Inspect more candidates before applying the final gate; this avoids top-k being
    # consumed by weak unrelated chunks.
    candidates = scored[:max(12, int(top_k) * 3)]
    results = []

    # Explicitly named process titles get a lower score floor because title evidence
    # is strong even when wording such as "kis team" does not overlap lexically.
    for score, idx in candidates:
        row = rows[idx].copy()
        title = str(row.get("title", ""))
        title_overlap = len(q_tokens & set(_tokenize(title)))
        if score < 0.055 and not title_overlap:
            continue
        if score < 0.035:
            continue
        row["score"] = round(float(score), 4)
        results.append(row)
        if len(results) >= max(int(top_k), 1):
            break

    # Grounding safety: a question about an explicitly named process must not be
    # answered from another process merely because it has similar vocabulary.
    named_processes = []
    for source_id, tokens in title_tokens.items():
        overlap = q_tokens & tokens
        if len(overlap) >= 1:
            named_processes.append((source_id, overlap))
    if named_processes:
        named_ids = {sid for sid, _ in named_processes}
        process_results = [r for r in results if r.get("source_type") == "process" and r.get("source_id") in named_ids]
        if process_results:
            others = [r for r in results if not (r.get("source_type") == "process" and r.get("source_id") not in named_ids)]
            results = process_results + others
            results = results[:max(int(top_k), 1)]

    # If the query contains a distinctive entity that is absent from the Business
    # Brain (e.g. "salon"), do not let generic words like "customer" or "process"
    # pull unrelated bakery evidence into the answer.
    informative = [t for t in q_tokens if len(t) >= 5 and t not in {
        "which", "where", "there", "about", "should", "would", "could",
        "people", "person", "roles", "role", "team", "teams", "staff",
        "handle", "handles", "responsible", "responsibility", "involved",
        "process", "customer", "customers", "order", "orders", "information",
        "required", "details", "before", "after", "creating", "creating",
        "business",
    }]
    if informative:
        corpus_tokens = set(_tokenize(" ".join(corpus)))
        matched = sum(1 for token in informative if token in corpus_tokens)
        if matched == 0:
            return []

    return results


def format_context(results):
    """Format retrieval results for the Gemini prompt."""
    blocks = []

    for i, row in enumerate(results, 1):
        blocks.append(
            f"[SOURCE {i}] "
            f"{row.get('title', 'Untitled')} "
            f"({row.get('source_type', 'knowledge')})\n"
            f"{row.get('content', '')}"
        )

    return "\n\n".join(blocks)


def bootstrap_index():
    """Keep the RAG index synchronized with current processes and knowledge."""
    from database import list_processes, list_knowledge

    processes = list_processes()
    knowledge_items = list_knowledge()

    current_process_ids = {int(p["id"]) for p in processes if p.get("id") is not None}
    current_knowledge_ids = {int(k["id"]) for k in knowledge_items if k.get("id") is not None}

    existing = list_chunks()
    for row in existing:
        source_type = row.get("source_type")
        try:
            source_id = int(row.get("source_id"))
        except (TypeError, ValueError):
            source_id = None
        if source_type == "process" and source_id not in current_process_ids:
            clear_chunks_for("process", source_id)
        elif source_type == "knowledge" and source_id not in current_knowledge_ids:
            clear_chunks_for("knowledge", source_id)

    # Re-index every process so older one-chunk indexes are upgraded to the new
    # semantic chunks, especially the dedicated People/Roles evidence chunk.
    for process in processes:
        index_process(process["id"], process)

    # Add missing knowledge chunks without disturbing existing knowledge data.
    existing = list_chunks()
    existing_knowledge_keys = {
        ("knowledge", x["source_id"])
        for x in existing if x.get("source_type") == "knowledge"
    }
    for item in knowledge_items:
        if ("knowledge", item["id"]) in existing_knowledge_keys:
            continue
        clear_chunks_for("knowledge", item["id"])
        for i, piece in enumerate(_chunk(item["content"]), 1):
            add_chunk("knowledge", item["id"], item["title"], piece,
                      {"chunk": i, "type": item["type"], "source": item["source"]})
