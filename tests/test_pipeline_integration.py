import sqlite3

from app import pipeline, store


def test_pipeline_persists_and_suppresses_duplicate(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "pipeline_test.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))

    # The pipeline imports these functions directly, so patch them there.
    monkeypatch.setattr(
        pipeline, "seen_recently", store.seen_recently
    )
    monkeypatch.setattr(
        pipeline, "record_alert", store.record_alert
    )
    monkeypatch.setattr(
        pipeline, "run_read_only_checks", lambda alert: {}
    )
    monkeypatch.setattr(
        pipeline,
        "triage_alert",
        lambda alert, checks: {"summary": "Integration test triage"},
    )
    monkeypatch.setattr(pipeline, "EMAIL_TO", "test@example.com")

    email_calls = []

    def fake_send_email(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr(pipeline, "send_email", fake_send_email)

    alert = {
        "source": "pytest",
        "title": "High CPU utilization",
        "status": "firing",
        "severity": "critical",
        "service": "checkout-api",
        "environment": "test",
        "dedup_key": "integration:checkout-api:high-cpu",
        "labels": {},
    }

    first_result = pipeline.process_alert(alert)
    second_result = pipeline.process_alert(alert)

    assert first_result["action"] == "triaged"
    assert first_result["notified"] is True
    assert second_result["action"] == "duplicate_suppressed"
    assert second_result["notified"] is False
    assert len(email_calls) == 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT status, service, title
            FROM alerts
            ORDER BY id
            """
        ).fetchall()

    assert rows == [
        ("notified", "checkout-api", "High CPU utilization"),
        (
            "suppressed_duplicate",
            "checkout-api",
            "High CPU utilization",
        ),
    ]
