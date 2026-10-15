from app.triage import _rule_based_triage

def test_cpu_alert_returns_safe_steps():
    alert = {"title": "High CPU", "message": "CPU over 90%", "service": "checkout", "severity": "critical"}
    result = _rule_based_triage(alert, {"performed": []})
    assert result["likely_cause"].startswith("Possible CPU")
    assert any("p95/p99" in step for step in result["recommended_steps"])
