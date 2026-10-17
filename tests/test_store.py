import sqlite3

from app import store


def test_record_alert_persists_to_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "test_alerts.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))

    alert = {
        "title": "High CPU utilization",
        "service": "checkout-api",
        "environment": "test",
        "dedup_key": "test:checkout-api:high-cpu",
    }

    store.record_alert(
        alert,
        status="notified",
        detail="Test notification recorded",
        dedup_key="hashed-test-key",
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT dedup_key, status, title, service, detail
            FROM alerts
            """
        ).fetchone()

    assert row == (
        "hashed-test-key",
        "notified",
        "High CPU utilization",
        "checkout-api",
        "Test notification recorded",
    )


def test_seen_recently_detects_persisted_alert(tmp_path, monkeypatch):
    db_path = tmp_path / "test_alerts.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))

    alert = {
        "title": "High CPU utilization",
        "service": "checkout-api",
        "environment": "test",
    }

    store.record_alert(
        alert,
        status="notified",
        detail="Notification sent",
        dedup_key="test-dedup-key",
    )

    assert store.seen_recently("test-dedup-key", 900) is True
    assert store.seen_recently("unknown-key", 900) is False
