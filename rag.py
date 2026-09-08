from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple

from database import (
    add_chunk,
    delete_chunks_for_source,
    list_chunks,
)


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize text for retrieval."""
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    """Simple tokenization for lightweight local retrieval."""
    text = normalize_text(text).lower()
    return re.findall(r"[a-zA-Z0-9_]+", text)


def chunk_text(
    text: str,
    chunk_size: int = 700,
    overlap: int = 120,
) -> List[str]:
    """
    Split text into overlapping chunks.

    This MVP uses character-based chunking so it stays lightweight
    and does not require an external embedding/vector database.
    """
    text = normalize_text(text)

    if not text:
        return []

    if chunk_size <= 0:
        chunk_size = 700

    if overlap < 0:
        overlap = 0

    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

    return chunks


# ---------------------------------------------------------
# Lightweight retrieval scoring
# ---------------------------------------------------------

def _term_frequency(tokens: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    return counts


def _cosine_similarity(
    query_counts: Dict[str, int],
    doc_counts: Dict[str, int],
) -> float:
    """Calculate cosine similarity between token-frequency vectors."""

    if not query_counts or not doc_counts:
        return 0.0

    common_terms = set(query_counts) & set(doc_counts)

    if not common_terms:
        return 0.0

    dot_product = sum(
        query_counts[token] * doc_counts[token]
        for token in common_terms
    )

    query_norm = math.sqrt(
        sum(value * value for value in query_counts.values())
    )

    doc_norm = math.sqrt(
        sum(value * value for value in doc_counts.values())
    )

    if query_norm == 0 or doc_norm == 0:
        return 0.0

    return dot_product / (query_norm * doc_norm)


def _keyword_overlap(
    query_tokens: List[str],
    doc_tokens: List[str],
) -> float:
    """
    Calculate how many unique query terms appear in the document.
    """

    query_unique = set(query_tokens)
    doc_unique = set(doc_tokens)

    if not query_unique:
        return 0.0

    overlap = query_unique & doc_unique

    return len(overlap) / len(query_unique)


def _score_chunk(query: str, text: str) -> float:
    """
    Combine cosine similarity and keyword overlap.

    This gives us a simple retrieval layer that can later be replaced
    with embeddings/vector search without changing the rest of the app.
    """

    query_tokens = tokenize(query)
    doc_tokens = tokenize(text)

    if not query_tokens or not doc_tokens:
        return 0.0

    query_counts = _term_frequency(query_tokens)
    doc_counts = _term_frequency(doc_tokens)

    cosine = _cosine_similarity(query_counts, doc_counts)
    overlap = _keyword_overlap(query_tokens, doc_tokens)

    # Weighted score.
    score = (cosine * 0.65) + (overlap * 0.35)

    return float(score)


# ---------------------------------------------------------
# Ingestion
# ---------------------------------------------------------

def ingest_text_knowledge(
    source_id: int,
    text: str,
    chunk_size: int = 700,
    overlap: int = 120,
) -> int:
    """
    Delete previous chunks for a knowledge source and index the
    new text.

    Returns the number of chunks created.
    """

    text = normalize_text(text)

    if not text:
        raise ValueError("The source did not contain readable content.")

    chunks = chunk_text(
        text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not chunks:
        raise ValueError("The source did not contain readable content.")

    # Remove old chunks first so updating a knowledge item does not
    # leave stale content behind.
    delete_chunks_for_source(source_id)

    for index, chunk in enumerate(chunks):
        add_chunk(
            source_id=source_id,
            chunk_index=index,
            content=chunk,
        )

    return len(chunks)


# ---------------------------------------------------------
# Retrieval
# ---------------------------------------------------------

def retrieve(
    query: str,
    top_k: int = 5,
    min_score: float = 0.07,
) -> List[Dict]:
    """
    Retrieve the most relevant knowledge chunks.

    The min_score threshold is important:
    unrelated questions should return no evidence instead of
    returning weak/irrelevant bakery information.
    """

    query = normalize_text(query)

    if not query:
        return []

    all_chunks = list_chunks()

    if not all_chunks:
        return []

    scored: List[Tuple[float, Dict]] = []

    for row in all_chunks:
        content = row.get("content", "")

        score = _score_chunk(
            query=query,
            text=content,
        )

        if score >= min_score:
            item = dict(row)
            item["score"] = round(score, 6)
            scored.append((score, item))

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        item
        for _, item in scored[:max(1, top_k)]
    ]


# ---------------------------------------------------------
# Retrieval context
# ---------------------------------------------------------

def build_context(results: List[Dict]) -> str:
    """
    Convert retrieval results into context that can be passed
    to the AI model.
    """

    if not results:
        return ""

    parts = []

    for index, result in enumerate(results, start=1):
        source_title = (
            result.get("title")
            or result.get("source_title")
            or f"Source {index}"
        )

        content = result.get("content", "").strip()

        if not content:
            continue

        parts.append(
            f"[Source {index}: {source_title}]\n"
            f"{content}"
        )

    return "\n\n".join(parts)


# ---------------------------------------------------------
# Source formatting
# ---------------------------------------------------------

def format_sources(results: List[Dict]) -> List[Dict]:
    """
    Return clean source metadata for the UI.
    """

    sources = []

    seen = set()

    for result in results:
        source_id = result.get("source_id")

        title = (
            result.get("title")
            or result.get("source_title")
            or "Untitled source"
        )

        key = (
            source_id,
            title,
        )

        if key in seen:
            continue

        seen.add(key)

        sources.append(
            {
                "source_id": source_id,
                "title": title,
                "type": result.get("type"),
                "score": result.get("score", 0.0),
            }
        )

    return sources

def format_context(results):
    return build_context(results)
def ingest_knowledge_file(source_id: int, file_data) -> int:
    """
    Read an uploaded knowledge file and index its text.
    """
    filename = getattr(file_data, "name", "").lower()

    if filename.endswith((".txt", ".md")):
        text = file_data.getvalue().decode("utf-8", errors="ignore")

    elif filename.endswith(".csv"):
        text = file_data.getvalue().decode("utf-8", errors="ignore")

    else:
        raise ValueError(
            f"Unsupported file type: {filename}"
        )

    return ingest_text_knowledge(
        source_id=source_id,
        text=text,
    )


def index_process(process_id: int) -> int:
    """
    Index a saved process so it can be retrieved by Business Brain.
    """
    from database import get_process

    process = get_process(process_id)

    if not process:
        raise ValueError("Process not found.")

    parts = []

    for key in [
        "name",
        "purpose",
        "trigger",
        "inputs",
        "roles",
        "steps",
        "decisions",
        "output",
        "exceptions",
        "warnings",
        "tools",
    ]:
        value = process.get(key)

        if value:
            parts.append(f"{key}: {value}")

    text = "\n".join(parts)

    if not text.strip():
        raise ValueError("Process does not contain readable content.")

    return ingest_text_knowledge(
        source_id=process_id,
        text=text,
    )


def bootstrap_index() -> None:
    """
    Rebuild the retrieval index from existing knowledge.
    """
    chunks = list_chunks()

    # The MVP stores chunks directly in SQLite,
    # so existing chunks are already available for retrieval.
    # This function is kept for app compatibility.
    return None
