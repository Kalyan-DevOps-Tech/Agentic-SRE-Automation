import os
import re
import shutil
import subprocess


def run_read_only_checks(alert: dict) -> dict:
    """Collect bounded, read-only Kubernetes evidence when explicitly enabled."""
    evidence = {"performed": [], "notes": []}

    if os.getenv("ENABLE_KUBECTL_READONLY", "false").lower() != "true":
        evidence["notes"].append(
            "Kubernetes checks disabled; set ENABLE_KUBECTL_READONLY=true "
            "after configuring least-privilege cluster access."
        )
        return evidence

    kubectl = shutil.which("kubectl")
    if not kubectl:
        evidence["notes"].append(
            "kubectl is not installed or is not available on PATH."
        )
        return evidence

    labels = alert.get("labels") or {}
    namespace = labels.get("namespace")
    service = alert.get("service")

    # Validate namespace before passing it to kubectl.
    if not namespace or not re.fullmatch(
        r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", str(namespace)
    ):
        evidence["notes"].append(
            "A valid Kubernetes namespace label is required; checks skipped."
        )
        return evidence

    commands = []

    # If the workload follows the conventional app=<service> label,
    # this narrows the result. Otherwise inspect pods in the namespace.
    if service and re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", str(service)):
        commands.append([
            kubectl, "get", "pods", "-n", str(namespace),
            "-l", f"app={service}", "-o", "wide", "--request-timeout=6s"
        ])

    commands.extend([
        [
            kubectl, "get", "pods", "-n", str(namespace),
            "-o", "wide", "--request-timeout=6s"
        ],
        [
            kubectl, "get", "events", "-n", str(namespace),
            "--sort-by=.lastTimestamp", "--request-timeout=6s"
        ],
    ])

    # Avoid duplicate pod queries if the service label is unavailable.
    seen_commands = set()
    for cmd in commands:
        command_key = tuple(cmd)
        if command_key in seen_commands:
            continue
        seen_commands.add(command_key)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            evidence["performed"].append({
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-1000:],
            })
            if result.returncode != 0:
                evidence["notes"].append(
                    f"Read-only command failed (exit {result.returncode}): "
                    f"{' '.join(cmd[1:4])}"
                )
        except subprocess.TimeoutExpired:
            evidence["notes"].append(
                f"Read-only command timed out: {' '.join(cmd[1:4])}"
            )
        except OSError as exc:
            evidence["notes"].append(
                f"Could not execute kubectl command: {type(exc).__name__}"
            )

    return evidence
