# scripts/build_index.py
import os
import sqlite3
import json
from pathlib import Path

import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

# Paths (relative to project root)
DB_PATH = "assets/db/rag.db"
DATA_DIR = "assets/data/pdfs"
EMBED_MODEL_PATH = "assets/models/all-MiniLM-L6-v2"

# Chunking config
CHUNK_SIZE = 700      # characters per chunk
CHUNK_OVERLAP = 150   # overlap between chunks


def get_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split long text into overlapping chunks.
    Normalizes whitespace and uses a sliding window.
    """
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())  # collapse multiple spaces
    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end == length:
            break
        start = start + chunk_size - overlap

    return chunks


def create_db():
    """
    Create (or open) the SQLite database and ensure the docs table exists.
    Embeddings are stored as JSON text (no extensions needed).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    con = sqlite3.connect(DB_PATH)

    con.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            page INTEGER,
            text TEXT,
            embedding TEXT            -- JSON string of the vector
        );
    """)
    con.commit()
    return con


def index_pdfs():
    """
    Main indexing pipeline:
    - Find all PDFs in data/pdfs
    - Extract text per page
    - Chunk text
    - Embed with local MiniLM model
    - Store in db/rag.db as JSON-encoded embeddings
    """
    pdf_dir = Path(DATA_DIR)
    if not pdf_dir.exists():
        raise FileNotFoundError(f"{DATA_DIR} folder does not exist. Create it and add some PDFs.")

    # Load local embedding model
    print(f"Loading embedding model from {EMBED_MODEL_PATH} ...")
    model = SentenceTransformer(EMBED_MODEL_PATH)

    con = create_db()

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {DATA_DIR}. Add your PDF files and rerun.")
        return

    for pdf_path in pdf_files:
        print(f"\nIndexing: {pdf_path.name}")
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            if not text or not text.strip():
                continue

            chunks = get_chunks(text)
            print(f"  Page {page_num + 1}: {len(chunks)} chunks")

            for chunk in chunks:
                emb = model.encode(chunk).tolist()
                emb_json = json.dumps(emb)  # store as JSON text

                con.execute(
                    "INSERT INTO docs (source, page, text, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    (pdf_path.name, page_num + 1, chunk, emb_json)
                )

        con.commit()

    con.close()
    print("\n✅ Indexing complete. Embeddings stored in db/rag.db")


if __name__ == "__main__":
    index_pdfs()
