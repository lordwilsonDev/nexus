#!/usr/bin/env python3
"""N03 Import-surface hygiene — every top-level module imports cleanly.

A module that imports only at runtime (after the app has "started") is a
latent breakage: it passes smoke tests and fails in production. This
experiment imports every top-level .py module in the repo (api, gateway,
router, config, memory, cli, engines.*) and requires zero failures.

Serverless: import-only, no daemon, no network calls at import time.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("MSB_REPO", Path(__file__).resolve().parents[2]))
EVIDENCE_DIR = REPO / "artifacts" / "hygiene"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
PY = os.environ.get("MSB_PYTHON", "/opt/homebrew/Caskroom/miniforge/base/bin/python")


def new_record() -> dict[str, Any]:
    return {
        "experiment_id": "n03_import_surface",
        "skill": "installation-hygiene",
        "input": "import every top-level module (api, gateway, router, config, memory, cli, engines.*)",
        "environment": f"local CLI @ {REPO}",
        "failure_injected": "none — import surface check",
        "expected_behavior": "all top-level modules import with zero failures",
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


def top_level_modules() -> list[str]:
    """Top-level modules: standalone .py files in the repo root, not entrypoints."""
    mods = []
    for p in sorted(REPO.glob("*.py")):
        if p.name in ("api.py", "gateway.py", "router.py", "config.py",
                      "memory.py", "cli.py"):
            mods.append(p.stem)
    for p in sorted((REPO / "engines").glob("*.py")):
        if p.name != "__init__.py":
            mods.append(f"engines.{p.stem}")
    return mods


def main() -> int:
    record = new_record()
    start = dt.datetime.now(dt.timezone.utc)

    modules = top_level_modules()
    record["state_before"]["modules"] = modules

    probe = (
        "import sys, json, traceback\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        "mods = " + json.dumps(modules) + "\n"
        "results = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        __import__(m)\n"
        "        results.append({'module': m, 'ok': True})\n"
        "    except Exception as e:\n"
        "        results.append({'module': m, 'ok': False, 'error': str(e)[:150]})\n"
        "ok_all = all(r['ok'] for r in results)\n"
        "print(json.dumps({'ok': ok_all, 'results': results}))\n"
    )

    try:
        proc = subprocess.run(
            [PY, "-c", probe],
            capture_output=True, text=True, timeout=120, check=False,
        )
        out = (proc.stdout or "").strip()
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(out.splitlines()[-1] if out else "{}")
        except Exception:
            parsed = {"ok": False, "results": [],
                      "error": (out or proc.stderr or "")[-300:]}
        failed = [r for r in parsed.get("results", []) if not r.get("ok")]
        record["state_after"] = {
            "ok": parsed.get("ok"), "imported": len(parsed.get("results", [])),
            "failed": failed,
        }
        record["evidence"].append(
            f"imported={len(parsed.get('results', []))} failed={len(failed)}"
        )
        record["actual_behavior"] = (
            f"ok={parsed.get('ok')} imported={len(parsed.get('results', []))} "
            f"failed={len(failed)}"
        )
        if parsed.get("ok") and not failed:
            record["verdict"] = "pass"
            record["recovery"] = "all top-level modules import cleanly"
        else:
            record["verdict"] = "fail"
            for r in failed:
                record["errors"].append(f"{r.get('module')}: {r.get('error')}")
            if parsed.get("error"):
                record["errors"].append(str(parsed["error"]))
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
        "imported": record["state_after"].get("imported"),
        "failed": [f.get("module") for f in record["state_after"].get("failed", [])],
        "artifact": str(path),
    }, indent=2))
    return 0 if record["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
