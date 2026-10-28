"""SQLite storage: two tables, categories and recordings."""
import os
import sqlite3
from datetime import datetime, timezone

from classify import classify, normalize, session_number
from config import CATEGORIES, PAGE_SIZE

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    session_no INTEGER,
    created_at TEXT NOT NULL,
    file_id TEXT NOT NULL,
    file_unique_id TEXT UNIQUE,
    kind TEXT NOT NULL DEFAULT 'audio'
);
"""


def connect(path):
    folder = os.path.dirname(path)
    if folder and path != ":memory:":
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for name in CATEGORIES:
        conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (name,))
    conn.commit()
    return conn


def category_id(conn, name):
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def find_category(conn, text):
    """Find a section by exact or partial Arabic name. Returns a row or None."""
    want = normalize(text)
    if not want:
        return None
    rows = conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()
    for row in rows:
        if normalize(row["name"]) == want:
            return row
    for row in rows:
        if want in normalize(row["name"]):
            return row
    return None


def add_recording(conn, title, file_id, file_unique_id=None, kind="audio",
                  category=None, created_at=None):
    """Add a recording. Returns (id, category_name) or None for a duplicate."""
    title = (title or "").strip() or "تسجيل بدون عنوان"
    category = category or classify(title)
    cid = category_id(conn, category)
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        cur = conn.execute(
            "INSERT INTO recordings(title, title_norm, category_id, session_no, "
            "created_at, file_id, file_unique_id, kind) VALUES (?,?,?,?,?,?,?,?)",
            (title, normalize(title), cid, session_number(title), created_at,
             file_id, file_unique_id, kind),
        )
    except sqlite3.IntegrityError:
        return None
    conn.commit()
    return cur.lastrowid, category


_SELECT = (
    "SELECT r.id, r.title, r.session_no, r.created_at, c.name AS category "
    "FROM recordings r JOIN categories c ON c.id = r.category_id "
)


def get(conn, rec_id):
    return conn.execute(
        "SELECT r.*, c.name AS category FROM recordings r "
        "JOIN categories c ON c.id = r.category_id WHERE r.id = ?", (rec_id,)
    ).fetchone()


def search(conn, query, limit=PAGE_SIZE, offset=0):
    """All words of the query must appear in the title (after normalisation)."""
    words = normalize(query).split()
    if not words:
        return []
    where = " AND ".join(["r.title_norm LIKE ? ESCAPE '\\'"] * len(words))
    params = ["%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
              for w in words]
    sql = _SELECT + "WHERE " + where + " ORDER BY r.id DESC LIMIT ? OFFSET ?"
    return conn.execute(sql, params + [limit, offset]).fetchall()


def by_category(conn, cat_id, limit=PAGE_SIZE, offset=0):
    """Recordings of a section. Sessions with a number come first, in order."""
    sql = (_SELECT + "WHERE r.category_id = ? "
           "ORDER BY r.session_no IS NULL, r.session_no ASC, r.id DESC LIMIT ? OFFSET ?")
    return conn.execute(sql, (cat_id, limit, offset)).fetchall()


def latest(conn, limit=PAGE_SIZE):
    return conn.execute(_SELECT + "ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()


def set_category(conn, rec_id, category_name):
    cid = category_id(conn, category_name)
    if cid is None:
        return False
    cur = conn.execute("UPDATE recordings SET category_id = ? WHERE id = ?", (cid, rec_id))
    conn.commit()
    return cur.rowcount == 1


def counts(conn):
    return conn.execute(
        "SELECT c.name, COUNT(r.id) AS n FROM categories c "
        "LEFT JOIN recordings r ON r.category_id = c.id GROUP BY c.id ORDER BY c.id"
    ).fetchall()
