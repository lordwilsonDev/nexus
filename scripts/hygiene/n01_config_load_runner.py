#!/usr/bin/env python3
"""N01 Config-load hygiene — config.yaml loads into NexusConfig without error.

The NEXUS config is the contract every engine reads at startup. A broken
config.yaml or a field the loader can't parse fails at boot, not at test
time. This experiment imports config.py, loads CONFIG, and requires the
expected fields to be present and non-empty.

Serverless: no daemon, no network.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("MSB_REPO", Path(__file__).resolve().parents[2]))
EVIDENCE_DIR = REPO / "artifacts" / "hygiene"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
PY = os.environ.get("MSB_PYTHON", "/opt/homebrew/Caskroom/miniforge/base/bin/python")


def new_record() -> dict[str, Any]:
    return {
        "experiment_id": "n01_config_load",
        "skill": "configuration-hygiene",
        "input": "load_config(config.yaml) must parse and merge NEXUS/1.1.0/ollama.host",
        "environment": f"local CLI @ {REPO}",
        "failure_injected": "none — configuration integrity check",
        "expected_behavior": "config.yaml parses; the YAML's own values are present on the merged config",
        "actual_behavior": "",
        "latency_ms": 0,
        "errors": [],
        "state_before": {},
        "state_after": {},
        "recovery": "",
        "false_repair": False,
        "evidence": [],
        "verdict": "unknown",
    }


def save(record: dict[str, Any]) -> Path:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = EVIDENCE_DIR / f"{record['experiment_id']}_{ts}.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path


PROBE = r'''
import json, sys
sys.path.insert(0, str(%r))
try:
    from config import load_config, NexusConfig
    cfg = load_config(%r)
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
    sys.exit(1)
# The real contract: config.yaml must parse AND merge into NexusConfig,
# so the YAML's own values (name/version/ollama.host) must be present.
expected = {
    "name": "NEXUS",
    "version": "1.1.0",
    "ollama_host": "http://localhost:11434",
}
found = {}
for k, want in expected.items():
    if k == "ollama_host":
        v = getattr(getattr(cfg, "ollama", None), "host", None)
    else:
        v = getattr(cfg, k, None)
    found[k] = None if v is None else str(v)
missing = [k for k, want in expected.items()
           if found.get(k) is None or found[k] == "" or found[k] != want]
print(json.dumps({"ok": len(missing) == 0, "missing": missing, "found": found}))
''' % (str(REPO), str(REPO / "config.yaml"))


def main() -> int:
    record = new_record()
    start = dt.datetime.now(dt.timezone.utc)

    try:
        proc = subprocess.run(
            [PY, "-c", PROBE],
            capture_output=True, text=True, timeout=60, check=False,
        )
        out = (proc.stdout or "").strip()
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(out.splitlines()[-1] if out else "{}")
        except Exception:
            parsed = {"ok": False, "error": (out or proc.stderr or "")[-200:]}
        record["state_after"] = parsed
        record["evidence"].append(
            f"config load ok={parsed.get('ok')} missing={parsed.get('missing')} "
            f"found={parsed.get('found')}"
        )
        record["actual_behavior"] = (
            f"ok={parsed.get('ok')} missing={parsed.get('missing')} "
            f"error={parsed.get('error', '')}"
        )
        if parsed.get("ok"):
            record["verdict"] = "pass"
            record["recovery"] = "config.yaml loads cleanly; all expected fields present"
        else:
            record["verdict"] = "fail"
            record["errors"].append(str(parsed.get("error") or parsed.get("missing")))
    except Exception as e:
        record["verdict"] = "fail"
        record["errors"].append(str(e))
    finally:
        record["latency_ms"] = int(
            (dt.datetime.now(dt.timezone.utc) - start).total_seconds() * 1000
        )

    path = save(record)
    print(json.dumps({
        "experiment": record["experiment_id"],
        "verdict": record["verdict"],
        "missing": record["state_after"].get("missing"),
        "artifact": str(path),
    }, indent=2))
    return 0 if record["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
