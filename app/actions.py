import os
import subprocess

def run_read_only_checks(alert: dict) -> dict:
    """
    Safe-by-default evidence collection. Optional kubectl commands are read-only.
    Enable only where this service runs with a least-privilege Kubernetes identity.
    """
    evidence = {"performed": [], "notes": []}
    if os.getenv("ENABLE_KUBECTL_READONLY", "false").lower() != "true":
        evidence["notes"].append("Kubernetes checks disabled; enable explicitly with a least-privilege read-only kubeconfig.")
        return evidence

    namespace = alert.get("labels", {}).get("namespace")
    service = alert.get("service")
    if not namespace:
        evidence["notes"].append("No namespace label supplied; skipped kubectl checks.")
        return evidence

    commands = [
        ["kubectl", "get", "pods", "-n", str(namespace), "-o", "wide"],
        ["kubectl", "get", "events", "-n", str(namespace), "--sort-by=.lastTimestamp"]
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
            evidence["performed"].append({
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-1500:]
            })
        except Exception as exc:
            evidence["notes"].append(f"{' '.join(cmd)} failed: {type(exc).__name__}")
    return evidence
