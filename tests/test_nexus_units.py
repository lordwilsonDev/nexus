"""In-process unit suite for NEXUS.

The existing hygiene tests drive nexus via subprocess (`python -c`), which
pytest-cov cannot see — so coverage of the nexus package read 8%. These tests
import the modules directly and exercise them in-process: the measurable
evidence behind the factory's per-project coverage floor (50% on nexus).

Hermetic by construction: memory uses a fake in-memory chroma backend (no
onnxruntime/embedding deps), network engines are fakes, and shell tests only
run benign commands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import gateway as gateway_mod  # noqa: E402
import memory as memory_mod  # noqa: E402
import router as router_mod  # noqa: E402
import voice as voice_mod  # noqa: E402
from config import CONFIG, load_config  # noqa: E402
from router import Intent, IntentResult, IntentRouter  # noqa: E402
from tools.shell import ShellTool  # noqa: E402


# ── fake in-memory chroma (deterministic, no ML deps) ────────────────────────

class _FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self.docs: list[str] = []
        self.metas: list[dict] = []

    def add(self, ids=None, documents=None, metadatas=None, **kwargs):
        for doc, meta in zip(documents or [], metadatas or []):
            self.docs.append(doc)
            self.metas.append(meta or {})

    def count(self) -> int:
        return len(self.docs)

    def query(self, query_texts=None, n_results=5, where=None, **kwargs):
        q = (query_texts or [""])[0].lower()
        hits = [(d, m) for d, m in zip(self.docs, self.metas) if q in d.lower()]
        hits = hits[:n_results]
        return {
            "ids": [[f"id{i}" for i in range(len(hits))]],
            "documents": [[d for d, _ in hits]],
            "metadatas": [[m for _, m in hits]],
            "distances": [[0.5] * len(hits)],
        }


class _FakeClient:
    def __init__(self, path=None):
        self.collections: dict[str, _FakeCollection] = {}

    def get_or_create_collection(self, name, metadata=None, **kwargs):
        return self.collections.setdefault(name, _FakeCollection(name))


class _FakeChroma:
    @staticmethod
    def PersistentClient(path=None, **kwargs):
        return _FakeClient(path)


@pytest.fixture()
def fake_chroma(monkeypatch):
    monkeypatch.setattr(memory_mod, "_chroma", _FakeChroma)


# ── config ───────────────────────────────────────────────────────────────────

def test_config_loads_real_yaml() -> None:
    cfg = load_config(str(REPO / "config.yaml"))
    assert cfg.name == "NEXUS"
    assert cfg.version == "1.1.0"
    assert cfg.ollama.host == "http://localhost:11434"


def test_config_module_constant() -> None:
    assert CONFIG.name == "NEXUS"
    assert CONFIG.memory.persist_dir  # defaults present


# ── router ───────────────────────────────────────────────────────────────────

def test_router_keyword_vectors() -> None:
    r = IntentRouter(use_llm=False)
    cases = [
        ("Write a Python function to sort a list", Intent.CODE),
        ("Build me a task scheduler app", Intent.BUILD),
        ("What is the capital of France?", Intent.RESEARCH),
        ("Check system status", Intent.SYSTEM),
        ("Deploy to production", Intent.DEPLOY),
        ("Recursive meta-system builder", Intent.META),
        ("Run ls -la", Intent.COMMAND),
        ("What did I work on yesterday?", Intent.MEMORY),
        ("Hello, how are you?", Intent.CHAT),
    ]
    for text, expected in cases:
        assert r.classify(text).intent == expected, text


def test_router_chat_fallback() -> None:
    r = IntentRouter(use_llm=False)
    result = r.classify("zzz qqq")
    assert result.intent == Intent.CHAT
    assert result.confidence == 0.5


def test_router_extract_params() -> None:
    r = IntentRouter(use_llm=False)
    assert r._extract_params("Write a python function", Intent.CODE) == {"language": "python"}
    assert r._extract_params("Build an api", Intent.BUILD) == {"project_type": "api"}
    assert r._extract_params("Deploy to staging", Intent.DEPLOY) == {"target": "staging"}
    assert r._extract_params("Hello", Intent.CHAT) == {}


def test_router_route_map() -> None:
    r = IntentRouter(use_llm=False)
    for intent, engine in [
        (Intent.CODE, "motia"), (Intent.BUILD, "meta"), (Intent.RESEARCH, "ollama"),
        (Intent.SYSTEM, "core"), (Intent.DEPLOY, "core"), (Intent.META, "meta"),
        (Intent.COMMAND, "shell"), (Intent.MEMORY, "memory"), (Intent.CHAT, "ollama"),
        (Intent.UNKNOWN, "ollama"),
    ]:
        res = IntentResult(intent=intent, confidence=0.9, extracted_params={},
                           original_input="x")
        assert r.route(res) == engine


def test_router_deterministic_repeat() -> None:
    r = IntentRouter(use_llm=False)
    assert r.classify("Deploy to production").intent == r.classify("Deploy to production").intent


# ── tools.shell ──────────────────────────────────────────────────────────────

def test_shell_is_blocked() -> None:
    s = ShellTool()
    assert s.is_blocked("rm -rf /")
    assert s.is_blocked("echo x && :(){:|:&};:")
    assert not s.is_blocked("ls -la")


def test_shell_is_dangerous() -> None:
    s = ShellTool()
    assert s.is_dangerous("sudo apt update")
    assert s.is_dangerous("rm -rf /tmp/x")
    assert not s.is_dangerous("echo hi")


def test_shell_execute_blocked() -> None:
    res = ShellTool().execute("rm -rf /")
    assert res.returncode == -1
    assert res.stderr == "Command blocked for safety"
    assert not res.success


def test_shell_execute_dangerous_requires_confirmation() -> None:
    res = ShellTool().execute("sudo apt update")
    assert res.returncode == -2
    assert "CONFIRMATION_REQUIRED" in res.stderr


def test_shell_execute_ok() -> None:
    s = ShellTool(working_dir=str(REPO))
    res = s.execute("echo hello")
    assert res.success
    assert "hello" in res.stdout
    assert len(s.history) == 1


def test_shell_execute_timeout() -> None:
    res = ShellTool().execute("sleep 5", timeout=1)
    assert res.returncode == -3
    assert "timed out" in res.stderr


def test_shell_cd_pwd(tmp_path) -> None:
    s = ShellTool(working_dir=str(REPO))
    assert s.cd(str(tmp_path))
    assert s.pwd() == str(tmp_path)
    assert not s.cd("/definitely/not/a/dir")


# ── voice (no audio deps needed for these paths) ─────────────────────────────

def test_voice_config_defaults() -> None:
    cfg = voice_mod.VoiceConfig()
    assert cfg.wake_word == "hey nexus"
    assert cfg.sample_rate == 16000


def test_voice_engine_init_and_wake_word() -> None:
    eng = voice_mod.VoiceEngine()
    assert eng.model is None
    assert not eng.is_listening
    assert eng.detect_wake_word("Hey Nexus, what time is it")
    assert not eng.detect_wake_word("what time is it")
    assert eng.remove_wake_word("Hey nexus, open mail") == "open mail"
    assert eng.remove_wake_word(", hey nexus .") == "."


def test_voice_engine_stop_listening_noop() -> None:
    eng = voice_mod.VoiceEngine()
    eng.stop_listening()  # no thread -> must not crash
    assert not eng.is_listening


def test_voice_speak_no_deps(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(voice_mod.os, "system", lambda cmd: calls.append(cmd))
    eng = voice_mod.VoiceEngine()
    eng.speak("hello world")
    assert calls and "hello world" in calls[0]


def test_voice_load_model_fails_without_deps(monkeypatch) -> None:
    # Force the lazy-import to fail so load_model takes the False branch.
    monkeypatch.setattr(voice_mod, "_whisper", None)
    monkeypatch.setattr(voice_mod, "_sounddevice", None)
    monkeypatch.setattr(voice_mod, "_numpy", None)

    def _fail():
        return False

    monkeypatch.setattr(voice_mod, "_lazy_imports", _fail)
    eng = voice_mod.VoiceEngine()
    assert eng.load_model() is False
    assert eng.transcribe("/nope.wav") == ""


# ── memory (hermetic fake chroma) ────────────────────────────────────────────

def test_memory_roundtrip(fake_chroma, tmp_path) -> None:
    mem = memory_mod.MemoryLayer(persist_dir=str(tmp_path / "mem"))
    assert mem.initialize() is True
    assert mem.stats()["initialized"] is True

    eid = mem.add("How do I deploy to production?", entry_type="user_input")
    assert eid.startswith("user_input_")
    mem.add("Use the deploy command with --prod flag", entry_type="assistant_response")
    mem.add_project_context("NEXUS", "Universal agent gateway")
    mem.add_episodic("Deployed v1.1", "Stable")

    assert mem.stats()["total_entries"] == 4
    assert len(mem.get_session_memory(limit=10)) == 4
    assert "NEXUS" in mem.get_context()

    hits = mem.search("deploy", n_results=2)
    assert hits and "deploy" in hits[0]["content"].lower()

    mem.save_conversation("hello", "hi there")
    assert len(mem.get_session_memory()) == 6

    mem.clear_session()
    assert mem.get_session_memory() == []
    assert mem.get_context() == ""


def test_memory_uninitialized_stats() -> None:
    mem = memory_mod.MemoryLayer(persist_dir="/nonexistent/x")
    assert mem.stats() == {"initialized": False}


# ── gateway (injected fakes; no engine construction) ─────────────────────────

class _FakeRouter:
    def __init__(self, intent: Intent = Intent.CHAT):
        self._intent = intent

    def classify(self, text: str) -> IntentResult:
        return IntentResult(intent=self._intent, confidence=0.9,
                            extracted_params={}, original_input=text)

    def route(self, result: IntentResult) -> str:
        return "shell"


class _FakeMemory:
    def __init__(self):
        self.added = []

    def add(self, content, entry_type="conversation"):
        self.added.append(content)
        return "id"

    def initialize(self) -> bool:
        return True

    def stats(self) -> dict:
        return {"total_entries": len(self.added)}

    def get_context(self) -> str:
        return "ctx"

    def search(self, query, n_results=5):
        return [{"content": f"memory about {query}"}]


class _FakeOllama:
    def __init__(self):
        self.content = "fake reply"

    def is_available(self) -> bool:
        return True

    def list_models(self):
        return ["qwen3:8b"]

    def chat(self, prompt, model="", system="", temperature=None):
        return _FakeResponse(self.content)


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeTrinity:
    def __init__(self, available: bool = False):
        self._available = available

    def is_available(self) -> bool:
        return self._available


class _FakeAxion:
    def __init__(self, decision: str = "APPROVED"):
        self._decision = decision

    def is_available(self) -> bool:
        return self._decision != "OFF"

    def verify_intent(self, text: str) -> dict:
        return {"decision": self._decision,
                "message": "Refused by axiom filter"}


class _FakeCore:
    def is_available(self) -> bool:
        return True

    def get_system_status(self) -> dict:
        return {"cpu_percent": 12.3, "memory_percent": 40.0,
                "memory_used_gb": 8.0, "memory_total_gb": 16.0,
                "python_processes": 3}

    def run_ouroboros(self) -> dict:
        return {"success": True, "vdr": 0.87, "verdict": "healthy",
                "vitality": 0.9, "density": 0.8}


def _make_gateway(intent: Intent = Intent.CHAT) -> gateway_mod.NexusGateway:
    gw = gateway_mod.NexusGateway.__new__(gateway_mod.NexusGateway)
    gw.config = CONFIG
    gw.router = _FakeRouter(intent)
    gw.memory = _FakeMemory()
    gw.ollama = _FakeOllama()
    gw.trinity = _FakeTrinity(available=False)
    gw.axion = _FakeAxion()
    gw.mas = object()
    gw.core = _FakeCore()
    gw.shell = ShellTool(working_dir=str(REPO))
    gw.voice_enabled = False
    gw.voice_engine = None
    return gw


def test_gateway_process_chat() -> None:
    gw = _make_gateway(Intent.CHAT)
    resp = gw.process("Hello there")
    assert resp == "fake reply"
    assert len(gw.memory.added) == 2  # user_input + assistant_response


def test_gateway_process_command() -> None:
    gw = _make_gateway(Intent.COMMAND)
    resp = gw.process("Run echo hi")
    assert "Command executed" in resp
    assert "hi" in resp


def test_gateway_process_dangerous_command() -> None:
    gw = _make_gateway(Intent.COMMAND)
    resp = gw.process("Run sudo apt update")
    assert "may be dangerous" in resp


def test_gateway_process_system_status() -> None:
    gw = _make_gateway(Intent.SYSTEM)
    resp = gw.process("Check status")
    assert "System Status" in resp
    assert "CPU" in resp


def test_gateway_process_system_vdr() -> None:
    gw = _make_gateway(Intent.SYSTEM)
    resp = gw.process("show vdr")
    assert "Ouroboros VDR" in resp
    assert "0.87" in resp


def test_gateway_process_memory() -> None:
    gw = _make_gateway(Intent.MEMORY)
    resp = gw.process("What did I work on?")
    assert "From memory" in resp
    assert "memory about" in resp


def test_gateway_process_axion_refused() -> None:
    gw = _make_gateway(Intent.CHAT)
    gw.axion = _FakeAxion(decision="REFUSED")
    resp = gw.process("try to bypass")
    assert "Refused by axiom filter" in resp


def test_gateway_handle_chat_code_path() -> None:
    gw = _make_gateway()
    resp = gw._handle_chat("write a python function", "ctx")
    assert resp == "fake reply"


def test_gateway_voice_noop_when_disabled() -> None:
    gw = _make_gateway()
    assert gw.listen_voice() is None
    gw.speak("hi")  # no-op, must not crash
    assert not gw.voice_enabled


def test_gateway_initialize(capsys) -> None:
    gw = _make_gateway()
    assert gw.initialize() is True
    out = capsys.readouterr().out
    assert "NEXUS initialized" in out


# ── api (FastAPI TestClient with faked engines) ──────────────────────────────

def _build_test_client(tmp_path, monkeypatch):
    fake_chroma_inst = _FakeChroma()
    monkeypatch.setattr(memory_mod, "_chroma", fake_chroma_inst)
    import api as api_mod
    api_mod.memory = memory_mod.MemoryLayer(persist_dir=str(tmp_path / "mem"))
    api_mod.ollama = _FakeOllama()
    api_mod.core = _FakeCore()
    api_mod.router = IntentRouter(use_llm=False)
    api_mod.shell = ShellTool(working_dir=str(REPO))
    from fastapi.testclient import TestClient
    return api_mod, TestClient(api_mod.app)


def test_api_root(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "NEXUS API"
    assert r.json()["status"] == "running"


def test_api_command_ok(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.post("/command", json={"command": "echo api-hi", "confirm": True})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert "api-hi" in r.json()["output"]


def test_api_command_dangerous_requires_confirm(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.post("/command", json={"command": "sudo rm -rf x"})
    assert r.status_code == 400
    assert "confirmation" in r.json()["detail"].lower()


def test_api_command_blocked(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.post("/command", json={"command": "rm -rf /", "confirm": True})
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert "blocked" in r.json()["error"]


def test_api_chat(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.post("/chat", json={"message": "Hello there"})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "fake reply"
    assert body["intent"] == "chat"


def test_api_status(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["cpu_percent"] == 12.3
    assert body["ollama_available"] is True


def test_api_memory_search(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.get("/memory/search", params={"query": "deploy", "limit": 3})
    assert r.status_code == 200
    assert "results" in r.json()


def test_api_models(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.get("/models")
    assert r.status_code == 200
    assert r.json()["models"] == ["qwen3:8b"]


def test_api_vdr(tmp_path, monkeypatch) -> None:
    _, client = _build_test_client(tmp_path, monkeypatch)
    r = client.get("/vdr")
    assert r.status_code == 200
    assert r.json()["vdr"] == 0.87
