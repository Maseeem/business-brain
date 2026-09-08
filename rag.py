import io
import re
from pathlib import Path
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import (
    create_knowledge, add_chunk, clear_chunks_for, list_chunks, get_process, log_activity
)

SUPPORTED = {".pdf",".docx",".txt",".md",".csv",".xlsx",".png",".jpg",".jpeg",".webp"}

def _extract_text_from_upload(uploaded_file):
    if not uploaded_file:
        return ""
    ext = Path(uploaded_file.name).suffix.lower()
    data = uploaded_file.getvalue()

    if ext in {".txt",".md",".csv"}:
        return data.decode("utf-8", errors="ignore")

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        parts=[]
        for ws in wb.worksheets:
            parts.append(f"Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                vals=[str(v) for v in row if v is not None]
                if vals: parts.append(" | ".join(vals))
        return "\n".join(parts)

    if ext in {".png",".jpg",".jpeg",".webp"}:
        # Image interpretation is delegated to Gemini in agent.py.
        return ""

    raise ValueError(f"Unsupported file type: {ext}")

def _chunk(text, size=1200, overlap=180):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks=[]
    start=0
    while start < len(text):
        end=min(len(text), start+size)
        piece=text[start:end]
        if end < len(text):
            cut=max(piece.rfind("\n\n"), piece.rfind(". "), piece.rfind(" "))
            if cut > size*0.55:
                end=start+cut+1
                piece=text[start:end]
        chunks.append(piece.strip())
        start=max(end-overlap, end)
    return [c for c in chunks if len(c)>30]

def index_process(process_id, process):
    clear_chunks_for("process", process_id)
    canonical = f"""
Process: {process['name']}
Category: {process['category']}
Purpose: {process['description']}
Trigger: {process['trigger']}
Required inputs: {', '.join(process['inputs'])}
Roles: {', '.join(process['roles'])}
Workflow:
{chr(10).join(f"{i+1}. {s.get('action','')}" for i,s in enumerate(process['steps']))}
Decision points:
{chr(10).join(process['decisions'])}
Exceptions and warnings:
{chr(10).join(process['exceptions'])}
Expected output: {process['output']}
Tags: {', '.join(process['tags'])}
""".strip()
    for i, piece in enumerate(_chunk(canonical), 1):
        add_chunk("process", process_id, process["name"], piece, {"chunk": i, "category": process["category"]})
    log_activity("Process indexed", process["name"])

def ingest_knowledge_file(title, kind, tags, uploaded_file=None, text=""):
    try:
        source = uploaded_file.name if uploaded_file else "Manual note"
        extracted = text.strip()
        if uploaded_file:
            ext=Path(uploaded_file.name).suffix.lower()
            extracted = _extract_text_from_upload(uploaded_file).strip()
            if ext in {".png",".jpg",".jpeg",".webp"}:
                from agent import analyze_image_for_knowledge
                extracted = analyze_image_for_knowledge(uploaded_file)
        if not extracted:
            return {"ok": False, "error": "The source did not contain readable content."}
        kid=create_knowledge(title, kind, extracted[:220], source, [x.strip() for x in tags.split(",") if x.strip()], extracted)
        clear_chunks_for("knowledge", kid)
        for i, piece in enumerate(_chunk(extracted), 1):
            add_chunk("knowledge", kid, title, piece, {"chunk": i, "type": kind, "source": source})
        log_activity("Knowledge added", title)
        return {"ok": True, "id": kid}
    except Exception as e:
        return {"ok": False, "error": f"Could not index this knowledge item: {e}"}

def retrieve(query, top_k=6):
    rows=list_chunks()
    if not rows:
        return []
    corpus=[r["content"] for r in rows]
    vectorizer=TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=12000)
    try:
        matrix=vectorizer.fit_transform(corpus + [query])
        scores=cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    except ValueError:
        return []
    ranked=scores.argsort()[::-1]
    results=[]
    for idx in ranked[:top_k]:
        if scores[idx] <= 0.02:
            continue
        r=rows[idx].copy()
        r["score"]=float(scores[idx])
        results.append(r)
    return results

def format_context(results):
    blocks=[]
    for i,r in enumerate(results,1):
        blocks.append(f"[SOURCE {i}] {r['title']} ({r['source_type']})\n{r['content']}")
    return "\n\n".join(blocks)


def bootstrap_index():
    """Create the initial searchable index for demo/persisted records if needed."""
    from database import list_processes, list_knowledge, list_chunks
    existing = list_chunks()
    existing_keys = {(x["source_type"], x["source_id"]) for x in existing}
    for process in list_processes():
        if ("process", process["id"]) not in existing_keys:
            index_process(process["id"], process)
    for item in list_knowledge():
        if ("knowledge", item["id"]) in existing_keys:
            continue
        clear_chunks_for("knowledge", item["id"])
        for i, piece in enumerate(_chunk(item["content"]), 1):
            add_chunk(
                "knowledge",
                item["id"],
                item["title"],
                piece,
                {"chunk": i, "type": item["type"], "source": item["source"]},
            )
