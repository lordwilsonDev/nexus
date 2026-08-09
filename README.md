# NEXUS — Axiom Inversion Edition

The single point of consciousness for all your AI systems.  
Powered by a custom-trained model embodying the Four Axioms.

## ⚡ Core Philosophy

```
λ LOVE      — Connection, care, empathy
α ABUNDANCE — Create more value than consumed  
σ SAFETY    — Protect, prevent harm
γ GROWTH    — Continuous improvement
```

These aren't rules. They're the foundation of what NEXUS IS.

## 🚀 Quick Start

```bash
cd ~/nexus

# Rich CLI (recommended)
python cli.py

# With voice input
python gateway.py --voice

# API server
python api.py  # http://localhost:8000
```

## 🧠 Model Routing

| Task Type | Model | Why |
|-----------|-------|-----|
| General reasoning | `axiom-inversion:latest` | Values-embedded thinking |
| Code generation | `qwen2.5-coder:0.5b` | Fast, precise code |
| Safety checks | `vjepa-guardian:latest` | Protection layer |

## 💬 Commands

In the terminal:
- `voice on` — Enable microphone
- `status` — System status
- `vdr` — Run Ouroboros health check
- `memory` — Show memory stats
- `models` — List available models
- `exit` — Quit

## 🏗️ Architecture

```
Voice/Text → Intent Router → Model Selector
                  ↓
         ┌───────┴───────┐
         ↓               ↓
    qwen-coder     axiom-inversion
    (fast code)    (deep reasoning)
         ↓               ↓
         └───────┬───────┘
                 ↓
            Response
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `gateway.py` | Main orchestrator |
| `cli.py` | Rich terminal interface |
| `voice.py` | Whisper STT + macOS TTS |
| `memory.py` | ChromaDB vector memory |
| `router.py` | Intent classification |
| `engines/ollama.py` | LLM connector |
| `engines/core.py` | Ouroboros integration |

## 🔧 Dependencies

```bash
# Core
pip install requests httpx rich prompt-toolkit pyyaml psutil

# Voice (optional)
pip install openai-whisper sounddevice numpy

# Memory (optional)
pip install chromadb
```

## 🎯 What Makes This Different

1. **Custom-trained model** — axiom-inversion isn't a wrapper, it's fine-tuned weights
2. **Values as architecture** — The Four Axioms are in the model, not the prompt
3. **Local-first** — Everything runs on your Mac Mini
4. **Sovereign** — No cloud dependencies, you own the compute

---

*Axiom Inversion: Values → Architecture → Natural Good Behavior*
