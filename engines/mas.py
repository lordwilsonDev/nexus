#!/usr/bin/env python3
"""
NEXUS Engine Connector for MAS (Multi-Agent System)
Bridges the Gateway to Yin (Forensics) and Yang (Synthesis).
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

MAS_PATH = Path.home() / "pure-python-mas"

class MASEngine:
    """Connector for the forensic and synthetic agent swarm."""
    
    def __init__(self):
        self._is_available = MAS_PATH.exists()
        
    def is_available(self) -> bool:
        return self._is_available
    
    def analyze_failure(self, file_path: str) -> str:
        """Run Yin forensic analysis on a file."""
        cmd = [sys.executable, str(MAS_PATH / "xcode_forensic.py"), file_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return f"Forensic analysis failed: {e}"
            
    def synthesize_solution(self, entity_type: str, name: str) -> str:
        """Run Yang synthesis to create code."""
        cmd = [sys.executable, str(MAS_PATH / "yang_synthesizer.py"), entity_type, name]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return f"Synthesis failed: {e}"

def get_mas():
    return MASEngine()
