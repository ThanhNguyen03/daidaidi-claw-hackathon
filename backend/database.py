"""
SQLite Database Module (data/app.db)
=====================================
Zero-install, zero-RAM overhead persistence for:
- Users (Auth + Role Management)
- Sessions (Chat History + Brief + Constraints)
- Org Rules (Admin-configurable Agent Learning)
- Agent Knowledge (Uploaded documents)

Preserved permanently across deployments via backend/data/app.db.
"""

from __future__ import annotations

import os
import sqlite3
import json
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.normpath(os.path.join(_HERE, "data", "app.db"))
_SECRET_KEY = os.getenv("SECRET_KEY", "adtimabox-secret-hackathon-2026-key")


def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize all tables if they don't exist yet."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'sales_rep',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT NOT NULL DEFAULT 'New Session',
                    brief_json TEXT,
                    messages_json TEXT,
                    constraints_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'all',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'all',
                    uploaded_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                );
            """)
        print(f"[database] SQLite ready at {_DB_PATH}")
    finally:
        conn.close()


def _user_count() -> int:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
        return row["c"]
    finally:
        conn.close()


# =============================================================================
# Password & Token Helpers
# =============================================================================

def hash_password(password: str) -> str:
    salt = hashlib.sha256(_SECRET_KEY.encode()).hexdigest()[:16]
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}:{pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, pwd_hash = stored_hash.split(":", 1)
        check = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(pwd_hash, check)
    except Exception:
        return False


def create_token(user_id: int, username: str) -> str:
    ts = datetime.utcnow().isoformat()
    data = f"{user_id}:{username}:{ts}"
    sig = hmac.new(_SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}:{sig}"


def verify_token(token: str) -> Optional[dict[str, Any]]:
    try:
        parts = token.split(":")
        # data has 3 parts (user_id, username, timestamp) + signature at the end
        if len(parts) < 4:
            return None
        # last part is the signature, rest is data
        sig = parts[-1]
        data = ":".join(parts[:-1])
        expected = hmac.new(_SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        user_id_str, username = parts[0], parts[1]
        return {"user_id": int(user_id_str), "username": username}
    except Exception:
        return None


# =============================================================================
# User Operations
# =============================================================================

def register_user(username: str, password: str, full_name: str) -> dict[str, Any]:
    """Register a new user. First user ever auto-becomes admin."""
    role = "admin" if _user_count() == 0 else "sales_rep"
    conn = get_db_connection()
    try:
        pwd_hash = hash_password(password)
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                (username.strip().lower(), pwd_hash, full_name.strip(), role),
            )
            user_id = cur.lastrowid
        token = create_token(user_id, username.strip().lower())
        return {
            "id": user_id,
            "username": username.strip().lower(),
            "full_name": full_name.strip(),
            "role": role,
            "token": token,
        }
    except sqlite3.IntegrityError:
        raise ValueError("Tên đăng nhập đã tồn tại")
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            raise ValueError("Tên đăng nhập hoặc mật khẩu không đúng")
        token = create_token(user["id"], user["username"])
        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "token": token,
        }
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, username, full_name, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_all_users() -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, username, full_name, role, created_at FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_user_role(user_id: int, new_role: str) -> None:
    allowed = {"admin", "account_manager", "sales_rep"}
    if new_role not in allowed:
        raise ValueError(f"Role không hợp lệ: {new_role}")
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    finally:
        conn.close()


# =============================================================================
# Session Persistence
# =============================================================================

def db_save_session(
    session_id: str,
    user_id: Optional[int],
    title: str,
    brief_data: dict,
    messages_data: list,
    constraints_data: list,
) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (session_id, user_id, title, brief_json, messages_json, constraints_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id            = COALESCE(excluded.user_id, sessions.user_id),
                    title              = excluded.title,
                    brief_json         = excluded.brief_json,
                    messages_json      = excluded.messages_json,
                    constraints_json   = excluded.constraints_json,
                    updated_at         = CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    user_id,
                    (title or "New Session")[:100],
                    json.dumps(brief_data, ensure_ascii=False),
                    json.dumps(messages_data, ensure_ascii=False),
                    json.dumps(constraints_data, ensure_ascii=False),
                ),
            )
    except Exception as e:
        print(f"[database] error saving session {session_id}: {e}")
    finally:
        conn.close()


def db_load_session(session_id: str) -> Optional[dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "brief": json.loads(row["brief_json"]) if row["brief_json"] else {},
            "messages": json.loads(row["messages_json"]) if row["messages_json"] else [],
            "constraints": json.loads(row["constraints_json"]) if row["constraints_json"] else [],
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        print(f"[database] error loading session {session_id}: {e}")
        return None
    finally:
        conn.close()


def db_list_user_sessions(user_id: Optional[int], limit: int = 30) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        if user_id:
            rows = conn.execute(
                """
                SELECT session_id, title, updated_at FROM sessions
                WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT session_id, title, updated_at FROM sessions
                ORDER BY updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()



# =============================================================================
# Org Rules (Admin Learning System)
# =============================================================================

def list_org_rules(scope: Optional[str] = None) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        if scope and scope != "all":
            rows = conn.execute(
                "SELECT * FROM org_rules WHERE scope IN ('all', ?) ORDER BY id",
                (scope,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM org_rules ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_active_rules(scope: Optional[str] = None) -> list[str]:
    """Return list of active rule content strings to inject into prompts."""
    conn = get_db_connection()
    try:
        if scope and scope != "all":
            rows = conn.execute(
                "SELECT content FROM org_rules WHERE is_active=1 AND scope IN ('all', ?) ORDER BY id",
                (scope,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT content FROM org_rules WHERE is_active=1 ORDER BY id"
            ).fetchall()
        return [r["content"] for r in rows]
    finally:
        conn.close()


def create_org_rule(title: str, content: str, scope: str, created_by: int) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO org_rules (title, content, scope, created_by) VALUES (?, ?, ?, ?)",
                (title.strip(), content.strip(), scope, created_by),
            )
            return dict(conn.execute("SELECT * FROM org_rules WHERE id = ?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


def update_org_rule(rule_id: int, title: str, content: str, scope: str, is_active: bool) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE org_rules SET title=?, content=?, scope=?, is_active=? WHERE id=?",
                (title.strip(), content.strip(), scope, int(is_active), rule_id),
            )
    finally:
        conn.close()


def delete_org_rule(rule_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM org_rules WHERE id = ?", (rule_id,))
    finally:
        conn.close()


def toggle_org_rule(rule_id: int, is_active: bool) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE org_rules SET is_active=? WHERE id=?",
                (int(is_active), rule_id),
            )
    finally:
        conn.close()
