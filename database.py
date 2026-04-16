import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional

DB_PATH = "outreach.db"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY,
                name TEXT,
                company TEXT,
                role TEXT,
                location TEXT,
                industry TEXT,
                linkedin_url TEXT,
                email TEXT,
                inner_condition TEXT,
                decision_driver TEXT,
                intelligence_hook TEXT,
                fit_score INTEGER,
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP,
                contacted_at TIMESTAMP,
                source TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                target_id INTEGER,
                message_type TEXT,
                content TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY(target_id) REFERENCES targets(id)
            );

            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY,
                date TEXT,
                targets_discovered INTEGER DEFAULT 0,
                targets_contacted INTEGER DEFAULT 0,
                replies_received INTEGER DEFAULT 0,
                meetings_booked INTEGER DEFAULT 0,
                created_at TIMESTAMP
            );
            """
        )


def insert_target(target: Dict, db_path: str = DB_PATH) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO targets (
                name, company, role, location, industry, linkedin_url, email,
                inner_condition, decision_driver, intelligence_hook, fit_score,
                status, created_at, contacted_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.get("name"),
                target.get("company"),
                target.get("role"),
                target.get("location"),
                target.get("industry"),
                target.get("linkedin_url"),
                target.get("email"),
                target.get("inner_condition"),
                target.get("decision_driver"),
                target.get("intelligence_hook"),
                target.get("fit_score"),
                target.get("status", "Pending"),
                target.get("created_at", now),
                target.get("contacted_at"),
                target.get("source", "manual"),
            ),
        )
        return int(cur.lastrowid)


def upsert_discovered_target(target: Dict, db_path: str = DB_PATH) -> Optional[int]:
    linkedin_url = (target.get("linkedin_url") or "").strip()
    if linkedin_url:
        with get_connection(db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM targets WHERE linkedin_url = ?",
                (linkedin_url,),
            ).fetchone()
            if existing:
                return None
    target.setdefault("source", "serpapi")
    return insert_target(target, db_path)


def get_target(target_id: int, db_path: str = DB_PATH) -> Optional[Dict]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
    return dict(row) if row else None


def list_targets(db_path: str = DB_PATH) -> List[Dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM targets ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def update_profile(target_id: int, profile: Dict, db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE targets
            SET inner_condition = ?, decision_driver = ?, intelligence_hook = ?, fit_score = ?
            WHERE id = ?
            """,
            (
                profile.get("inner_condition"),
                profile.get("decision_driver"),
                profile.get("intelligence_hook"),
                profile.get("fit_score"),
                target_id,
            ),
        )


def replace_messages(target_id: int, messages: Dict[str, str], db_path: str = DB_PATH) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM messages WHERE target_id = ?", (target_id,))
        for msg_type, content in messages.items():
            conn.execute(
                "INSERT INTO messages (target_id, message_type, content, created_at) VALUES (?, ?, ?, ?)",
                (target_id, msg_type, content, now),
            )


def get_messages_for_target(target_id: int, db_path: str = DB_PATH) -> Dict[str, str]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT message_type, content FROM messages WHERE target_id = ?",
            (target_id,),
        ).fetchall()
    return {row["message_type"]: row["content"] for row in rows}


def update_status(target_id: int, status: str, db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE targets SET status = ? WHERE id = ?", (status, target_id))


def mark_contacted(target_id: int, db_path: str = DB_PATH) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE targets SET status = 'Contacted', contacted_at = ? WHERE id = ?",
            (now, target_id),
        )


def _get_or_create_daily_log(date_str: str, db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM daily_logs WHERE date = ?", (date_str,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO daily_logs (date, created_at) VALUES (?, ?)",
                (date_str, datetime.utcnow().isoformat()),
            )


def increment_daily(field: str, amount: int = 1, db_path: str = DB_PATH) -> None:
    field_queries = {
        "targets_discovered": "UPDATE daily_logs SET targets_discovered = targets_discovered + ? WHERE date = ?",
        "targets_contacted": "UPDATE daily_logs SET targets_contacted = targets_contacted + ? WHERE date = ?",
        "replies_received": "UPDATE daily_logs SET replies_received = replies_received + ? WHERE date = ?",
        "meetings_booked": "UPDATE daily_logs SET meetings_booked = meetings_booked + ? WHERE date = ?",
    }
    query = field_queries.get(field)
    if not query:
        raise ValueError("Unsupported daily log field")

    date_str = datetime.utcnow().date().isoformat()
    _get_or_create_daily_log(date_str, db_path)
    with get_connection(db_path) as conn:
        conn.execute(query, (amount, date_str))


def get_today_contacted_count(db_path: str = DB_PATH) -> int:
    date_str = datetime.utcnow().date().isoformat()
    _get_or_create_daily_log(date_str, db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT targets_contacted FROM daily_logs WHERE date = ?",
            (date_str,),
        ).fetchone()
    return int(row["targets_contacted"] if row else 0)


def get_today_summary(db_path: str = DB_PATH) -> Dict:
    date_str = datetime.utcnow().date().isoformat()
    _get_or_create_daily_log(date_str, db_path)
    with get_connection(db_path) as conn:
        log = conn.execute("SELECT * FROM daily_logs WHERE date = ?", (date_str,)).fetchone()
        top_targets = conn.execute(
            """
            SELECT name, company, fit_score
            FROM targets
            WHERE substr(created_at, 1, 10) = ?
            ORDER BY COALESCE(fit_score, 0) DESC, id DESC
            LIMIT 3
            """,
            (date_str,),
        ).fetchall()
        updates = conn.execute(
            """
            SELECT name, company, status
            FROM targets
            WHERE status IN ('Replied', 'Meeting Booked')
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()
    return {
        "date": date_str,
        "log": dict(log) if log else {},
        "top_targets": [dict(r) for r in top_targets],
        "status_updates": [dict(r) for r in updates],
    }


def export_rows(db_path: str = DB_PATH) -> Iterable[Dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT t.*, 
                   MAX(CASE WHEN m.message_type='connection' THEN m.content END) AS connection_message,
                   MAX(CASE WHEN m.message_type='followup' THEN m.content END) AS followup_message,
                   MAX(CASE WHEN m.message_type='email' THEN m.content END) AS email_message
            FROM targets t
            LEFT JOIN messages m ON t.id = m.target_id
            GROUP BY t.id
            ORDER BY t.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]
