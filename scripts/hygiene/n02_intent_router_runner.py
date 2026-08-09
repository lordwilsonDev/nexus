#!/usr/bin/env python3

"""N02 Intent-router hygiene — IntentRouter(use_llm=False) is deterministic.

The router is the entry point for every NEXUS interaction. With use_llm=False
the classification is pure keyword matching — it MUST be deterministic (same
input → same intent) and MUST route known keyword intents to the expected
engines (the router's own __main__ test vectors). If the router wobbles or
mis-routes, every downstream engine gets the wrong work.

Serverless: use_llm=False never touches Ollama.
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
PY = os.environ.get("MSB_PYTHON", sys.executable)


def new_record() -> dict[str, Any]:
    return {
        "experiment_id": "n02_intent_router",
        "skill": "determinism",
        "input": (
            "IntentRouter(use_llm=False): 9 known test inputs classified twice; "
            "intent must be stable AND match the router's own expectations"
        ),
        "environment": f"local CLI @ {REPO}",
        "failure_injected": "none — determinism + routing contract check",
        "expected_behavior": (
            "repeated classification is identical; known keyword intents "
            "route to the expected engines"
        ),
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
from router import IntentRouter, Intent

router = IntentRouter(use_llm=False)

# (input, expected_intent) — the router's own __main__ vectors.
cases = [
    ("Write a Python function to sort a list", "code"),
    ("Build me a task scheduler app", "build"),
    ("What is the capital of France?", "research"),
    ("Check system status", "system"),
    ("Deploy to production", "deploy"),
    ("Run ls -la", "command"),
    ("What did I work on yesterday?", "memory"),
    ("Hello, how are you?", "chat"),
]

results = []
for text, expected in cases:
    r1 = router.classify(text)
    r2 = router.classify(text)
    engine = router.route(r1)
    results.append({
        "input": text[:40],
        "expected": expected,
        "intent_run1": r1.intent.value,
        "intent_run2": r2.intent.value,
        "engine": engine,
        "stable": r1.intent == r2.intent,
        "correct": r1.intent.value == expected,
    })

all_stable = all(r["stable"] for r in results)
all_correct = all(r["correct"] for r in results)
print(json.dumps({"ok": all_stable and all_correct,
                  "all_stable": all_stable, "all_correct": all_correct,
                  "cases": results}))
''' % (str(REPO),)


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
            parsed = {"ok": False, "error": (out or proc.stderr or "")[-300:]}
        record["state_after"] = parsed
        wrong = [c["input"] for c in parsed.get("cases", []) if not c.get("correct")]
        unstable = [c["input"] for c in parsed.get("cases", []) if not c.get("stable")]
        record["evidence"].append(
            f"router stable={parsed.get('all_stable')} correct={parsed.get('all_correct')} "
            f"wrong={wrong} unstable={unstable}"
        )
        record["actual_behavior"] = (
            f"all_stable={parsed.get('all_stable')} all_correct={parsed.get('all_correct')} "
            f"wrong={wrong} unstable={unstable}"
        )
        if parsed.get("ok"):
            record["verdict"] = "pass"
            record["recovery"] = (
                "keyword intent classification is deterministic and routes "
                "all known test vectors correctly"
            )
        else:
            record["verdict"] = "fail"
            if wrong:
                record["errors"].append(f"mis-routed: {wrong}")
            if unstable:
                record["errors"].append(f"non-deterministic: {unstable}")
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
        "all_stable": record["state_after"].get("all_stable"),
        "all_correct": record["state_after"].get("all_correct"),
        "artifact": str(path),
    }, indent=2))
    return 0 if record["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
