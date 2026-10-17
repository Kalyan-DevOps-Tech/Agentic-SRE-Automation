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


def test_pipeline_persists_email_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "email_failure.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))
    monkeypatch.setattr(pipeline, "seen_recently", store.seen_recently)
    monkeypatch.setattr(pipeline, "record_alert", store.record_alert)
    monkeypatch.setattr(pipeline, "run_read_only_checks", lambda alert: {})
    monkeypatch.setattr(
        pipeline,
        "triage_alert",
        lambda alert, checks: {"summary": "SMTP failure integration test"},
    )
    monkeypatch.setattr(pipeline, "EMAIL_TO", "test@example.com")

    def failing_email(**kwargs):
        raise RuntimeError("Simulated SMTP failure")

    monkeypatch.setattr(pipeline, "send_email", failing_email)

    alert = {
        "source": "pytest",
        "title": "High CPU utilization",
        "status": "firing",
        "severity": "critical",
        "service": "checkout-api",
        "environment": "test",
        "dedup_key": "integration:checkout-api:smtp-failure",
        "labels": {},
    }

    result = pipeline.process_alert(alert)

    assert result["action"] == "triaged"
    assert result["notified"] is False

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, service FROM alerts"
        ).fetchall()

    assert rows == [("email_failed", "checkout-api")]


def test_pipeline_records_resolved_alert_without_email(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "resolved_alert.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))
    monkeypatch.setattr(pipeline, "record_alert", store.record_alert)

    email_calls = []

    def fake_send_email(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr(pipeline, "send_email", fake_send_email)

    alert = {
        "source": "pytest",
        "title": "High CPU utilization",
        "status": "resolved",
        "severity": "critical",
        "service": "checkout-api",
        "environment": "test",
        "dedup_key": "integration:checkout-api:resolved",
        "labels": {},
    }

    result = pipeline.process_alert(alert)

    assert result["action"] == "resolved_recorded"
    assert result["notified"] is False
    assert email_calls == []

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, service FROM alerts"
        ).fetchall()

    assert rows == [("resolved", "checkout-api")]


def test_webhook_persists_alert_and_suppresses_duplicate(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient
    from app import main

    db_path = tmp_path / "webhook_integration.db"
    monkeypatch.setattr(store, "DB_PATH", str(db_path))
    monkeypatch.setattr(pipeline, "seen_recently", store.seen_recently)
    monkeypatch.setattr(pipeline, "record_alert", store.record_alert)
    monkeypatch.setattr(
        pipeline, "run_read_only_checks", lambda alert: {}
    )
    monkeypatch.setattr(
        pipeline,
        "triage_alert",
        lambda alert, checks: {
            "summary": "Webhook integration test passed"
        },
    )
    monkeypatch.setattr(pipeline, "EMAIL_TO", "test@example.com")

    email_calls = []

    def fake_send_email(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr(pipeline, "send_email", fake_send_email)

    client = TestClient(main.app)

    alert = {
        "source": "pytest",
        "title": "High CPU utilization",
        "status": "firing",
        "severity": "critical",
        "service": "checkout-api",
        "environment": "test",
        "dedup_key": "webhook:checkout-api:high-cpu",
        "labels": {},
    }

    first_response = client.post("/webhook/alert", json=alert)
    second_response = client.post("/webhook/alert", json=alert)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_body = first_response.json()
    second_body = second_response.json()

    assert first_body["action"] == "triaged"
    assert first_body["notified"] is True
    assert second_body["action"] == "duplicate_suppressed"
    assert second_body["notified"] is False
    assert len(email_calls) == 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, service FROM alerts ORDER BY id"
        ).fetchall()

    assert rows == [
        ("notified", "checkout-api"),
        ("suppressed_duplicate", "checkout-api"),
    ]
