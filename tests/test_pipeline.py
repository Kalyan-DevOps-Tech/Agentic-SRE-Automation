import pytest
from fastapi.testclient import TestClient

from app import main, pipeline


@pytest.fixture
def sample_alert():
    return {
        "source": "pytest",
        "alert_id": "test-001",
        "title": "High CPU utilization",
        "status": "firing",
        "severity": "critical",
        "service": "checkout-api",
        "environment": "test",
        "message": "CPU utilization exceeded 90%",
        "dedup_key": "test:checkout-api:high-cpu",
        "labels": {},
    }


@pytest.fixture
def isolate_pipeline(monkeypatch):
    records = []

    monkeypatch.setattr(
        pipeline, "seen_recently", lambda key, cooldown: False
    )
    monkeypatch.setattr(
        pipeline, "record_alert",
        lambda alert, status, summary, dedup_key=None:
            records.append(status)
    )
    monkeypatch.setattr(
        pipeline, "run_read_only_checks", lambda alert: {}
    )
    monkeypatch.setattr(
        pipeline, "triage_alert",
        lambda alert, checks: {"summary": "Test triage complete"}
    )
    monkeypatch.setattr(pipeline, "EMAIL_TO", "test@example.com")

    return records


def test_critical_alert_triggers_email(
    monkeypatch, sample_alert, isolate_pipeline
):
    emails = []

    monkeypatch.setattr(
        pipeline,
        "send_email",
        lambda **kwargs: emails.append(kwargs) or True,
    )

    result = pipeline.process_alert(sample_alert)

    assert result["accepted"] is True
    assert result["action"] == "triaged"
    assert result["notified"] is True
    assert len(emails) == 1
    assert "CRITICAL" in emails[0]["subject"]


def test_duplicate_alert_is_suppressed(
    monkeypatch, sample_alert, isolate_pipeline
):
    emails = []
    monkeypatch.setattr(
        pipeline,
        "seen_recently",
        lambda key, cooldown: True,
    )
    monkeypatch.setattr(
        pipeline,
        "send_email",
        lambda **kwargs: emails.append(kwargs) or True,
    )

    result = pipeline.process_alert(sample_alert)

    assert result["action"] == "duplicate_suppressed"
    assert result["notified"] is False
    assert emails == []
    assert "suppressed_duplicate" in isolate_pipeline


def test_resolved_alert_does_not_send_email(
    monkeypatch, sample_alert, isolate_pipeline
):
    emails = []
    monkeypatch.setattr(
        pipeline,
        "send_email",
        lambda **kwargs: emails.append(kwargs) or True,
    )
    sample_alert["status"] = "resolved"

    result = pipeline.process_alert(sample_alert)

    assert result["action"] == "resolved_recorded"
    assert result["notified"] is False
    assert emails == []
    assert "resolved" in isolate_pipeline


def test_invalid_webhook_token_returns_401(monkeypatch):
    monkeypatch.setattr(main, "WEBHOOK_TOKEN", "test-secret")
    client = TestClient(main.app)

    response = client.post(
        "/webhook/alert",
        json={
            "title": "Test alert",
            "severity": "critical",
        },
        headers={"X-Webhook-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook token"

def test_smtp_failure_is_handled_safely(
    monkeypatch, sample_alert, isolate_pipeline, caplog
):
    import logging
    def fail_email(**kwargs):
        raise RuntimeError("Simulated SMTP failure")

    monkeypatch.setattr(pipeline, "send_email", fail_email)

    result = pipeline.process_alert(sample_alert)

    assert result["accepted"] is True
    assert result["action"] == "triaged"
    assert result["notified"] is False
    assert "email_failed" in isolate_pipeline
