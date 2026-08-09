"""Real pytest suite for NEXUS — the evidence behind the factory's
`regression_passed` gate field for this project.

Mirrors the three hygiene experiments at unit level: config loads, the
keyword intent router is deterministic and routes known vectors correctly,
and every top-level module imports. All serverless (use_llm=False / import
only) — no daemon, no network.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, "-c", code],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_config_loads_with_expected_fields() -> None:
    """config.yaml parses and merges: NEXUS/1.1.0/ollama.host all present."""
    code = f"""
import sys, json
sys.path.insert(0, {str(REPO)!r})
from config import load_config
cfg = load_config({str(REPO / 'config.yaml')!r})
expected = {{"name": "NEXUS", "version": "1.1.0",
            "ollama_host": "http://localhost:11434"}}
found = {{"name": cfg.name, "version": cfg.version,
          "ollama_host": getattr(getattr(cfg, "ollama", None), "host", None)}}
missing = [k for k, want in expected.items() if found.get(k) != want]
print(json.dumps({{"missing": missing}}))
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert '"missing": []' in proc.stdout, proc.stdout[-2000:]


def test_intent_router_is_deterministic() -> None:
    """Same input classified twice yields the same intent (use_llm=False)."""
    code = f"""
import sys, json
sys.path.insert(0, {str(REPO)!r})
from router import IntentRouter
router = IntentRouter(use_llm=False)
inputs = ["Write a Python function", "Deploy to production", "Hello"]
results = []
for t in inputs:
    a = router.classify(t).intent.value
    b = router.classify(t).intent.value
    results.append({{"input": t, "a": a, "b": b, "stable": a == b}})
print(json.dumps({{"ok": all(r["stable"] for r in results), "results": results}}))
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = proc.stdout.strip()
    assert '"ok": true' in out, out[-2000:]


def test_intent_router_routes_known_vectors() -> None:
    """The router's own __main__ vectors classify to the expected intents."""
    code = f"""
import sys, json
sys.path.insert(0, {str(REPO)!r})
from router import IntentRouter
router = IntentRouter(use_llm=False)
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
wrong = [t for t, exp in cases if router.classify(t).intent.value != exp]
print(json.dumps({{"wrong": wrong}}))
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert '"wrong": []' in proc.stdout, proc.stdout[-2000:]


def test_all_top_level_modules_import() -> None:
    """api, gateway, router, config, memory, cli and engines.* import cleanly."""
    mods = ["api", "gateway", "router", "config", "memory", "cli",
            "engines.core", "engines.ollama", "engines.trinity"]
    code = (
        f"import sys, json\nsys.path.insert(0, {str(REPO)!r})\n"
        "failed = []\n"
        "for m in " + repr(mods) + ":\n"
        "    try:\n        __import__(m)\n"
        "    except Exception as e:\n        failed.append({'module': m, 'error': str(e)[:150]})\n"
        "print(json.dumps({'failed': failed}))\n"
    )
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert '"failed": []' in proc.stdout, proc.stdout[-3000:]
