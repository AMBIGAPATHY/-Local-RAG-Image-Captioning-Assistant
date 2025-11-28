import os
import sqlite3
import json
from datetime import datetime

# You can override this with an env var if you want
DB_PATH = os.getenv("CHAT_DB_PATH", "assets/db/chat_history.db")


def _ensure_dir():
    directory = os.path.dirname(DB_PATH)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def _get_conn():
    _ensure_dir()
    # check_same_thread=False so we can use it in Dash callbacks
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _ensure_schema():
    """
    Create tables if they don't exist and migrate older schemas to have
    a `content` column on messages, so new code doesn't crash with
    'no such column: content'.
    """
    con = _get_conn()
    cur = con.cursor()

    # --- chats table ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # --- messages table (new schema) ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT,         -- main text of the message
            meta TEXT,            -- JSON (e.g. for image captions, etc.)
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
        """
    )

    # --- migrate older schemas if needed ---
    cur.execute("PRAGMA table_info(messages);")
    cols_info = cur.fetchall()
    col_names = [row["name"] for row in cols_info]

    # If table existed without `content` column, add it.
    if "content" not in col_names:
        cur.execute("ALTER TABLE messages ADD COLUMN content TEXT;")

    # If there was an older `text` column, copy it into `content`
    if "text" in col_names:
        cur.execute("UPDATE messages SET content = text WHERE content IS NULL;")

    # Ensure meta exists (older schema might miss it)
    if "meta" not in col_names:
        cur.execute("ALTER TABLE messages ADD COLUMN meta TEXT;")

    con.commit()
    con.close()


# Run schema check/migration on import
_ensure_schema()


# ---------------------------------------------------------------------
# API functions expected by app_dash.py
# ---------------------------------------------------------------------

def init_db():
    """
    Backwards-compatible init function used by app_dash.py.
    Safe to call multiple times.
    """
    _ensure_schema()


def get_chats():
    """
    Return list of chats ordered by last update:
    [
      {"id": 1, "title": "Chat 1", "updated_at": "..."},
      ...
    ]
    """
    con = _get_conn()
    cur = con.cursor()
    cur.execute(
        """
        SELECT id, title, updated_at
        FROM chats
        ORDER BY datetime(updated_at) DESC, id DESC
        """
    )
    rows = cur.fetchall()
    con.close()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def list_chats():
    """
    Wrapper so older code calling `list_chats()` still works.
    app_dash.py imports list_chats, so we just delegate to get_chats().
    """
    return get_chats()


def get_or_create_default_chat():
    """
    If no chats exist yet, create one 'New chat' and return its id.
    Otherwise return the most recently updated chat.
    """
    con = _get_conn()
    cur = con.cursor()
    cur.execute("SELECT id FROM chats ORDER BY datetime(updated_at) DESC, id DESC LIMIT 1")
    row = cur.fetchone()

    if row:
        chat_id = row["id"]
    else:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)",
            ("New chat", now, now),
        )
        chat_id = cur.lastrowid
        con.commit()

    con.close()
    return chat_id


def create_chat(title: str | None = None) -> int:
    """
    Create a new chat and return its id.
    """
    if not title or not title.strip():
        title = "New chat"

    now = datetime.utcnow().isoformat()

    con = _get_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)",
        (title, now, now),
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id


def rename_chat(chat_id: int, new_title: str):
    """
    Rename a chat.
    """
    if not new_title or not new_title.strip():
        return

    now = datetime.utcnow().isoformat()
    con = _get_conn()
    cur = con.cursor()
    cur.execute(
        "UPDATE chats SET title=?, updated_at=? WHERE id=?",
        (new_title.strip(), now, chat_id),
    )
    con.commit()
    con.close()


def delete_chat(chat_id: int):
    """
    Delete a chat and all its messages.
    """
    con = _get_conn()
    cur = con.cursor()
    # Delete messages first for safety (FOREIGN KEY with CASCADE should also handle it)
    cur.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    cur.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()


# ---------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------

def add_message(chat_id: int, role: str, content: str, meta: dict | None = None) -> int:
    """
    Insert a message into a chat and update chat.updated_at.
    role: 'user' or 'assistant' (or others if you use them)
    content: the text to display in the chat bubble
    meta: optional dict (e.g. image caption, tags, etc.)
    """
    if meta is None:
        meta_json = None
    else:
        meta_json = json.dumps(meta, ensure_ascii=False)

    now = datetime.utcnow().isoformat()

    con = _get_conn()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO messages (chat_id, role, content, meta, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chat_id, role, content, meta_json, now),
    )

    msg_id = cur.lastrowid

    # bump chat updated_at
    cur.execute(
        "UPDATE chats SET updated_at=? WHERE id=?",
        (now, chat_id),
    )

    con.commit()
    con.close()
    return msg_id


def get_messages(chat_id: int):
    """
    Return messages for a chat in ascending order:
    [
      {"id": 1, "role": "user", "content": "...", "meta": {...}, "created_at": "..."},
      ...
    ]
    This matches what app_dash.py expects for rendering ChatGPT-style bubbles.
    """
    con = _get_conn()
    cur = con.cursor()

    # IMPORTANT: now this SELECT is safe because we always ensure `content` column exists
    cur.execute(
        """
        SELECT id, role, content, meta, created_at
        FROM messages
        WHERE chat_id=?
        ORDER BY id ASC
        """,
        (chat_id,),
    )
    rows = cur.fetchall()
    con.close()

    messages = []
    for row in rows:
        meta_raw = row["meta"]
        try:
            meta_obj = json.loads(meta_raw) if meta_raw else None
        except Exception:
            meta_obj = None

        messages.append(
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"] or "",
                "meta": meta_obj,
                "created_at": row["created_at"],
            }
        )

    return messages
