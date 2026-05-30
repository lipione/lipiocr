from __future__ import annotations

from pathlib import Path


def backup_readiness_report(root: str | Path = ".") -> dict[str, object]:
    base = Path(root)
    required = {
        "backup_script": base / "deploy/scripts/backup.sh",
        "restore_script": base / "deploy/scripts/restore.sh",
        "health_check": base / "deploy/scripts/health-check.sh",
        "incident_runbook": base / "docs/runbooks/incident-response.md",
        "dr_runbook": base / "docs/runbooks/disaster-recovery.md",
    }
    checks = {key: path.exists() for key, path in required.items()}
    return {
        "report": "backup_readiness",
        "checks": checks,
        "status": "ready" if all(checks.values()) else "incomplete",
    }
