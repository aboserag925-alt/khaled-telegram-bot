"""Supabase storage layer (REST / PostgREST) for the bot.

Replaces the old local SQLite file. Tables (schema public, already created):
  recordings(id, title, category, session_no, file_id, added_at)
  bot_users(user_id, first_seen)

Settings come from environment variables only:
  SUPABASE_URL          e.g. https://<project-ref>.supabase.co
  SUPABASE_SERVICE_KEY  the service_role key (server side only, never in code)
Row level security is on with no policies, so only the service key can read
and write. Never ship this key to a client or commit it.
"""
import os

import httpx

TIMEOUT = 15
# Tests set this to an httpx.MockTransport. Production leaves it None.
_transport = None


def _base():
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return url + "/rest/v1", key


async def _request(method, table, params=None, body=None, prefer=None, count=False):
    base, key = _base()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    prefs = [p for p in (prefer, "count=exact" if count else None) if p]
    if prefs:
        headers["Prefer"] = ",".join(prefs)
    async with httpx.AsyncClient(timeout=TIMEOUT, transport=_transport) as c:
        r = await c.request(method, f"{base}/{table}", params=params,
                            json=body, headers=headers)
    if r.status_code >= 400:
        # Never include headers (they carry the key) in the error text.
        raise RuntimeError(f"supabase {method} {table} -> {r.status_code}: {r.text[:200]}")
    return r


def _total(resp):
    """Total row count from the Content-Range header, e.g. '0-9/57' or '*/0'."""
    cr = resp.headers.get("content-range", "")
    tail = cr.rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _like(term):
    """Escape LIKE wildcards so the user's text is matched literally."""
    for ch in ("\\", "%", "_"):
        term = term.replace(ch, "\\" + ch)
    return term.replace("*", "")


async def check():
    """Startup check: fails loudly if the URL, key or tables are wrong."""
    await _request("GET", "recordings", {"select": "id", "limit": "1"})
    await _request("GET", "bot_users", {"select": "user_id", "limit": "1"})


async def user_exists(uid):
    r = await _request("GET", "bot_users", {"select": "user_id", "user_id": f"eq.{int(uid)}", "limit": "1"})
    return bool(r.json())


async def touch_user(uid):
    await _request("POST", "bot_users", {"on_conflict": "user_id"}, [{"user_id": int(uid)}],
                   prefer="resolution=ignore-duplicates,return=minimal")


async def save_recording(title, cat, no, file_id):
    await _request("POST", "recordings",
                   body=[{"title": title, "category": cat, "session_no": no, "file_id": file_id}],
                   prefer="return=minimal")


async def recordings_latest(limit):
    r = await _request("GET", "recordings", {"select": "id,title", "order": "id.desc", "limit": str(limit)})
    return r.json()


async def search_title(term, limit=20):
    r = await _request("GET", "recordings", {"select": "id,title", "title": f"ilike.*{_like(term)}*",
                                             "order": "id.asc", "limit": str(limit)})
    return r.json()


async def category_page(key, page, size):
    """Rows of one category ordered by session number (empty first) then id, plus the total."""
    r = await _request("GET", "recordings",
                       {"select": "id,title", "category": f"eq.{key}",
                        "order": "session_no.asc.nullsfirst,id.asc",
                        "limit": str(size), "offset": str(page * size)}, count=True)
    return r.json(), _total(r)


async def get_recording(rec_id):
    r = await _request("GET", "recordings",
                       {"select": "title,file_id", "id": f"eq.{int(rec_id)}", "limit": "1"})
    rows = r.json()
    return rows[0] if rows else None


async def count(table):
    r = await _request("GET", table, {"select": "id" if table == "recordings" else "user_id", "limit": "1"},
                       count=True)
    return _total(r)
