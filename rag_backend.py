import os
import io
import json
import base64
import sqlite3

import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# Paths for RAG index (must match scripts/build_index.py)
DB_PATH = os.getenv("RAG_DB_PATH", "assets/db/rag.db")
EMBED_MODEL_PATH = os.getenv("RAG_EMBED_MODEL", "assets/models/all-MiniLM-L6-v2")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_configured = False
_embed_model = None
_rag_texts = []
_rag_meta = []
_rag_embeddings = None  # numpy array [N, D]


def _configure():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY / GOOGLE_API_KEY in environment.")
    genai.configure(api_key=api_key)


def _ensure_config():
    global _configured
    if not _configured:
        _configure()
        _configured = True


def _load_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_PATH)
    return _embed_model


def _load_rag_index():
    """
    Load all embeddings + texts from the SQLite DB into memory (once).
    Expects a table like:
      docs(id INTEGER, source TEXT, page INTEGER, text TEXT, embedding TEXT_JSON)
    """
    global _rag_texts, _rag_meta, _rag_embeddings

    if _rag_embeddings is not None:
        return

    if not os.path.exists(DB_PATH):
        # No index yet – RAG will be skipped
        _rag_texts = []
        _rag_meta = []
        _rag_embeddings = np.zeros((0, 1), dtype="float32")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    try:
        cur.execute("SELECT id, source, page, text, embedding FROM docs")
    except sqlite3.Error:
        # Fallback if schema is different / db broken
        _rag_texts = []
        _rag_meta = []
        _rag_embeddings = np.zeros((0, 1), dtype="float32")
        con.close()
        return

    rows = cur.fetchall()
    con.close()

    texts = []
    meta = []
    embeds = []

    for row in rows:
        _id, source, page, text, emb_json = row
        try:
            emb = np.array(json.loads(emb_json), dtype="float32")
        except Exception:
            continue
        texts.append(text)
        meta.append({"id": _id, "source": source, "page": page})
        embeds.append(emb)

    if embeds:
        _rag_texts = texts
        _rag_meta = meta
        _rag_embeddings = np.vstack(embeds)
    else:
        _rag_texts = []
        _rag_meta = []
        _rag_embeddings = np.zeros((0, 1), dtype="float32")


def _semantic_search(query: str, top_k: int = 5):
    """
    Return top_k (context_text, meta, score) using cosine similarity.
    If RAG index doesn't exist, returns [].
    """
    _load_rag_index()
    if _rag_embeddings is None or _rag_embeddings.shape[0] == 0:
        return []

    model = _load_embed_model()
    q_vec = model.encode([query])[0].astype("float32")

    # cosine similarity
    emb = _rag_embeddings
    q_norm = np.linalg.norm(q_vec) + 1e-8
    e_norm = np.linalg.norm(emb, axis=1) + 1e-8
    sims = (emb @ q_vec) / (e_norm * q_norm)

    idx = np.argsort(-sims)[:top_k]
    results = []
    for i in idx:
        i = int(i)
        results.append((_rag_texts[i], _rag_meta[i], float(sims[i])))
    return results


def caption_image(b64_data: str):
    """
    Accepts the raw dcc.Upload 'contents' string, sends to Gemini, and
    returns dict: {caption, tags, raw_text}.
    """
    _ensure_config()
    if not b64_data:
        return {"caption": "", "tags": [], "raw_text": ""}

    # Strip "data:image/xxx;base64," prefix if present
    if "," in b64_data:
        _, b64_str = b64_data.split(",", 1)
    else:
        b64_str = b64_data

    try:
        img_bytes = base64.b64decode(b64_str)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:
        return {"caption": "", "tags": [], "raw_text": ""}

    # Optionally resize big images to save tokens
    max_side = 1024
    w, h = image.size
    if max(w, h) > max_side:
        scale = max_side / float(max(w, h))
        image = image.resize((int(w * scale), int(h * scale)))

    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = (
        "You are an image captioning assistant.\n"
        "1. Write a short, clear caption for this image.\n"
        "2. Generate 3 short keyword-style tags.\n"
        '3. Respond ONLY in strict JSON with keys: "caption", "tags".\n'
        'Example: {"caption": "...", "tags": ["tag1","tag2","tag3"]}'
    )

    response = model.generate_content([prompt, image])

    raw_text = response.text if hasattr(response, "text") else str(response)
    caption = ""
    tags = []

    # Robust JSON parse
    try:
        # Some models wrap JSON in ```json blocks
        import re

        m = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
        else:
            data = json.loads(raw_text)

        if isinstance(data, dict):
            caption = data.get("caption", "")
            tags = data.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            caption = ""
            tags = []
    except Exception:
        # Fallback: just return the raw text as caption
        caption = raw_text.strip()
        tags = []

    return {"caption": caption, "tags": tags, "raw_text": raw_text}


def answer_text(prompt: str) -> str:
    """
    Retrieval-augmented answer using local SQLite embeddings + Gemini 2.5 Flash.
    If the RAG index is missing, falls back to plain Gemini answer.
    """
    _ensure_config()
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Try RAG search
    contexts = _semantic_search(prompt, top_k=5)

    # No RAG context → simple LLM answer
    if not contexts:
        system_prompt = (
            "You are a helpful, concise assistant. "
            "Keep answers crisp and actionable."
        )
        resp = model.generate_content([system_prompt, prompt])
        return resp.text.strip() if resp and hasattr(resp, "text") else ""

    # Build context block
    context_chunks = []
    for text, meta, score in contexts:
        src = meta.get("source", "unknown")
        page = meta.get("page", "")
        context_chunks.append(f"Source: {src}, page {page}\n{text}")

    context_text = "\n\n---\n\n".join(context_chunks)

    system_prompt = (
        "You are a helpful RAG assistant.\n"
        "You are answering questions based ONLY on the context from local documents.\n"
        "If the context does not contain the answer, say you don't know or that it is not in the docs.\n"
        "Write clear, structured answers. If useful, you can mention the source filename and page.\n"
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"Context:\n{context_text}\n\n"
        f"User question:\n{prompt}"
    )

    resp = model.generate_content(full_prompt)
    return resp.text.strip() if resp and hasattr(resp, "text") else ""
