"""
NEXUS Configuration
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class OllamaConfig:
    host: str = "http://localhost:11434"
    default_model: str = "axiom-inversion:latest"  # Primary brain
    models: Dict[str, str] = field(default_factory=lambda: {
        "general": "axiom-inversion:latest",     # Values-embedded reasoning
        "code": "qwen2.5-coder:0.5b",             # Fast code tasks
        "reasoning": "axiom-inversion:latest",   # Deep thinking
        "fast": "qwen2.5-coder:0.5b",             # Quick classification
        "guardian": "vjepa-guardian:latest"       # Safety checks
    })


@dataclass
class VoiceConfig:
    enabled: bool = True
    wake_word: str = "hey nexus"
    whisper_model: str = "base"  # tiny, base, small, medium, large
    language: str = "en"
    tts_enabled: bool = True
    tts_voice: str = "com.apple.voice.compact.en-US.Samantha"


@dataclass
class MemoryConfig:
    persist_dir: str = "data/chromadb"
    collection_name: str = "nexus_memory"
    max_results: int = 10


@dataclass 
class EngineConfig:
    motia_url: str = "http://localhost:3000"
    core_path: str = str(Path.home() / "core")
    meta_path: str = str(Path.home() / "Meta")
    sparse_axion_path: str = str(Path.home() / "sparse_axion_rag")
    # Engine toggles + paths declared in config.yaml (hygiene n01 finding:
    # load_config crashed on these — config.yaml was being silently ignored).
    trinity: bool = False
    axion: bool = False
    mas: bool = False
    mas_path: str = str(Path.home() / "pure-python-mas")
    trinity_path: str = str(Path.home() / ".trinity")


@dataclass
class NexusConfig:
    name: str = "NEXUS"
    version: str = "1.0.0"
    home_dir: str = str(Path.home() / "nexus")
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    engines: EngineConfig = field(default_factory=EngineConfig)
    
    # Intent routing keywords
    intent_keywords: Dict[str, List[str]] = field(default_factory=lambda: {
        "code": ["code", "function", "class", "debug", "fix", "implement", "refactor"],
        "build": ["build", "create", "generate", "scaffold", "new project"],
        "research": ["research", "find", "search", "what is", "explain", "how to"],
        "system": ["status", "health", "process", "memory", "cpu", "running"],
        "deploy": ["deploy", "push", "release", "publish"],
        "meta": ["meta", "system builder", "evolve", "pattern"]
    })


def load_config(config_path: Optional[str] = None) -> NexusConfig:
    """Load configuration from YAML file or use defaults.

    Defaults to <repo>/config.yaml when present (hygiene n01 finding: the
    global CONFIG was built with no path, so the shipped YAML was never
    actually loaded — the app ran on defaults while config.yaml rotted).
    """
    if not config_path:
        candidate = Path(__file__).resolve().parent / "config.yaml"
        config_path = str(candidate) if candidate.exists() else None
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            # Merge with defaults
            config = NexusConfig()
            # Top-level scalar fields (hygiene n01 finding: name/version were
            # silently dropped, so the app reported 1.0.0 while config.yaml
            # declared 1.1.0).
            for scalar_key in ("name", "version", "home_dir"):
                if scalar_key in data:
                    setattr(config, scalar_key, data[scalar_key])
            if 'ollama' in data:
                config.ollama = OllamaConfig(**data['ollama'])
            if 'voice' in data:
                config.voice = VoiceConfig(**data['voice'])
            if 'memory' in data:
                config.memory = MemoryConfig(**data['memory'])
            if 'engines' in data:
                config.engines = EngineConfig(**data['engines'])
            return config
    return NexusConfig()


# Global config instance
CONFIG = load_config()
