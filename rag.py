import io
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


def index_process(process_id, process):
    """Turn a structured process into searchable chunks."""
    clear_chunks_for("process", process_id)

    canonical = f"""
Process: {process.get("name", "")}
Category: {process.get("category", "")}
Purpose: {process.get("description", "")}
Trigger: {process.get("trigger", "")}
Required inputs: {", ".join(process.get("inputs", []))}
Roles: {", ".join(process.get("roles", []))}
Workflow:
{chr(10).join(f"{i+1}. {s.get('action', '')}" for i, s in enumerate(process.get("steps", [])))}
Decision points:
{chr(10).join(process.get("decisions", []))}
Exceptions and warnings:
{chr(10).join(process.get("exceptions", []))}
Expected output: {process.get("output", "")}
Tags: {", ".join(process.get("tags", []))}
""".strip()

    for i, piece in enumerate(_chunk(canonical), 1):
        add_chunk(
            "process",
            process_id,
            process.get("name", "Untitled Process"),
            piece,
            {
                "chunk": i,
                "category": process.get("category", "Operations"),
            },
        )

    log_activity(
        "Process indexed",
        process.get("name", "Untitled Process"),
    )


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


def _expand_query(query):
    """Add lightweight business-language variants without changing the user's question."""
    text = re.sub(r"[^\w\s-]", " ", (query or "").casefold())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    # Small, deterministic vocabulary expansion helps natural-language questions
    # match the structured process vocabulary used in the index.
    aliases = {
        "order": "orders ordering",
        "orders": "order ordering",
        "place": "submit create receive",
        "placed": "submitted received created",
        "process": "workflow procedure steps handling",
        "work": "workflow process steps",
        "handle": "handling manage resolve",
        "handled": "handling manage resolve",
        "handling": "handle manage resolve",
        "complain": "complaint complaints issue concern",
        "complains": "complaint complaints complain issue concern",
        "complaint": "complaints complain issue concern handling",
        "complaints": "complaint complain issue concern handling",
        "customer": "customers client",
        "customers": "customer client",
        "information": "details requirements inputs",
        "required": "requirements needed necessary",
        "need": "required requirements necessary",
        "needed": "required requirements necessary",
        "steps": "workflow process procedure",
    }

    expanded = [text]
    for token in text.split():
        clean = token.strip("-_")
        if clean in aliases:
            expanded.append(aliases[clean])

    return " ".join(expanded)


def retrieve(query, top_k=6):
    """Retrieve relevant chunks using hybrid word + character TF-IDF.

    Word n-grams capture meaning and common phrases. Character n-grams make
    retrieval tolerant of spelling mistakes such as ``coustomer`` or
    ``complains`` while still ranking genuinely related business content first.
    """
    query = (query or "").strip()

    if not query:
        return []

    rows = list_chunks()

    if not rows:
        return []

    corpus = [str(r.get("content", "")) for r in rows]

    if not any(corpus):
        return []

    # Correct only very close spellings against words that actually exist in
    # the Business Brain. This keeps typo tolerance useful without silently
    # turning unrelated words into business terms.
    corpus_vocabulary = set(
        re.findall(r"[a-z0-9]+", " ".join(corpus).casefold())
    )
    raw_tokens = re.findall(r"[a-z0-9]+", query.casefold())
    corrected_tokens = []
    informative_matches = 0
    informative_unmatched = 0
    generic_tokens = {
        "how", "what", "when", "where", "why", "who", "does", "do",
        "did", "our", "your", "the", "a", "an", "is", "are", "to",
        "of", "for", "with", "and", "or", "can", "i", "we", "you",
        "my", "me", "in", "on", "about", "work", "handle", "process",
        "new", "place", "placed", "create", "creating", "receive", "receiving",
    }

    for token in raw_tokens:
        if token in corpus_vocabulary:
            corrected_tokens.append(token)
            if token not in generic_tokens:
                informative_matches += 1
            continue

        if len(token) >= 5:
            close = get_close_matches(
                token,
                corpus_vocabulary,
                n=1,
                cutoff=0.72,
            )
            if close:
                corrected_tokens.append(close[0])
                if token not in generic_tokens:
                    informative_matches += 1
                continue

        corrected_tokens.append(token)
        if token not in generic_tokens and len(token) >= 4:
            informative_unmatched += 1

    corrected_query = " ".join(corrected_tokens)
    expanded_query = _expand_query(corrected_query)

    # If the question contains specific terms that cannot be matched to the
    # stored business vocabulary, do not retrieve a generic-looking answer.
    # Example: a deleted/unsupported "salon appointment" question should not
    # accidentally retrieve a bakery complaint process just because both use
    # the word "customer".
    specific_tokens = [
        t for t in raw_tokens
        if t not in generic_tokens and len(t) >= 4
    ]
    if specific_tokens and informative_matches == 0:
        return []

    if (
        specific_tokens
        and informative_unmatched > 0
        and informative_unmatched / len(specific_tokens) >= 0.5
    ):
        return []

    try:
        word_vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=12000,
            sublinear_tf=True,
        )
        word_matrix = word_vectorizer.fit_transform(corpus + [expanded_query])
        word_scores = cosine_similarity(
            word_matrix[-1],
            word_matrix[:-1],
        ).flatten()
    except ValueError:
        word_scores = [0.0] * len(rows)

    try:
        char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            max_features=20000,
            sublinear_tf=True,
        )
        char_matrix = char_vectorizer.fit_transform(corpus + [query])
        char_scores = cosine_similarity(
            char_matrix[-1],
            char_matrix[:-1],
        ).flatten()
    except ValueError:
        char_scores = [0.0] * len(rows)

    results = []

    for idx, row in enumerate(rows):
        word_score = float(word_scores[idx])
        char_score = float(char_scores[idx])
        score = (0.60 * word_score) + (0.40 * char_score)

        # Give an additional small signal when the query contains terms that
        # appear in the source title. This is especially useful for questions
        # such as "how do we handle customer complaints?".
        title = str(row.get("title", "")).casefold()
        title_tokens = set(re.findall(r"[a-z0-9]+", title))
        query_tokens = set(re.findall(r"[a-z0-9]+", expanded_query))
        title_overlap = len(title_tokens & query_tokens)
        if title_overlap:
            score += min(0.14, 0.05 * title_overlap)

        # Keep only meaningful matches. The threshold is deliberately lower
        # than the old 0.07 cutoff because character similarity can produce
        # useful evidence for misspelled questions.
        if score < 0.045:
            continue

        item = row.copy()
        item["score"] = float(score)
        results.append(item)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:max(int(top_k), 1)]

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

    # Remove chunks belonging to deleted processes/knowledge
    current_process_ids = {
        int(p["id"])
        for p in processes
        if p.get("id") is not None
    }

    current_knowledge_ids = {
        int(k["id"])
        for k in knowledge_items
        if k.get("id") is not None
    }

    existing = list_chunks()

    for row in existing:
        source_type = row.get("source_type")
        source_id = row.get("source_id")

        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            source_id = None

        if source_type == "process" and source_id not in current_process_ids:
            clear_chunks_for("process", source_id)

        elif source_type == "knowledge" and source_id not in current_knowledge_ids:
            clear_chunks_for("knowledge", source_id)

    # Re-index all current processes
    for process in processes:
        index_process(
            process["id"],
            process,
        )

    # Index knowledge that does not already have chunks
    existing = list_chunks()

    existing_knowledge_keys = {
        ("knowledge", x["source_id"])
        for x in existing
        if x.get("source_type") == "knowledge"
    }

    for item in knowledge_items:
        if ("knowledge", item["id"]) in existing_knowledge_keys:
            continue

        clear_chunks_for(
            "knowledge",
            item["id"],
        )

        for i, piece in enumerate(_chunk(item["content"]), 1):
            add_chunk(
                "knowledge",
                item["id"],
                item["title"],
                piece,
                {
                    "chunk": i,
                    "type": item["type"],
                    "source": item["source"],
                },
            )
