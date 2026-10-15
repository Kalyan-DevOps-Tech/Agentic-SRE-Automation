import sqlite3
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv("DB_PATH", "/data/alerts.db")

def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dedup_key TEXT NOT NULL,
        received_at TEXT NOT NULL,
        status TEXT NOT NULL,
        title TEXT,
        service TEXT,
        detail TEXT
    )""")
    conn.commit()
    return conn

def seen_recently(dedup_key: str, cooldown_seconds: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts WHERE dedup_key=? AND received_at>=? AND status IN ('notified','triaged_email_not_configured','suppressed_duplicate') LIMIT 1",
            (dedup_key, cutoff)
        ).fetchone()
    return row is not None

def record_alert(alert: dict, status: str, detail: str, dedup_key: str | None = None):
    dedup_key = dedup_key or alert.get("dedup_key") or f"{alert.get('environment','unknown')}|{alert.get('service','unknown')}|{alert.get('title','unknown')}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO alerts(dedup_key, received_at, status, title, service, detail) VALUES(?,?,?,?,?,?)",
            (dedup_key, datetime.now(timezone.utc).isoformat(), status, alert.get("title"), alert.get("service"), detail)
        )
        conn.commit()
