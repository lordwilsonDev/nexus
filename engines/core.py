"""
NEXUS - Core Engine Connector

Connects to Python engines in ~/core/:
- Ouroboros (VDR self-judgment)
- Discovery Agent
- Healing Agent
- Optimization Agent
- Master Orchestrator
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Add core to path
CORE_PATH = Path.home() / "core"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))


class CoreEngines:
    """
    Connector for Python engines in ~/core/
    """
    
    def __init__(self):
        self.core_path = CORE_PATH
        self._ouroboros = None
        
    def is_available(self) -> bool:
        """Check if core engines are available."""
        return self.core_path.exists() and (self.core_path / "ouroboros.py").exists()
    
    def run_ouroboros(self) -> Dict[str, Any]:
        """Run Ouroboros VDR check."""
        try:
            # Import and run
            if self._ouroboros is None:
                import ouroboros
                self._ouroboros = ouroboros
            
            engine = self._ouroboros.OuroborosEngine()
            vdr, metrics = engine.calculate_vdr()
            
            return {
                "success": True,
                "vdr": vdr,
                "verdict": metrics.get("verdict", "unknown"),
                "vitality": metrics.get("vitality", 0),
                "density": metrics.get("density", 0)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status using core engines."""
        import psutil
        
        # Get basic metrics
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Count Python processes
        python_count = sum(1 for p in psutil.process_iter(['name']) 
                         if 'python' in p.info['name'].lower())
        
        return {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "python_processes": python_count,
            "core_available": self.is_available()
        }
    
    def run_discovery(self, target: str = ".") -> Dict[str, Any]:
        """Run discovery agent on a target path."""
        try:
            import discovery_agent
            # This would call the discovery agent
            return {"success": True, "message": "Discovery agent not fully integrated yet"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_healing(self) -> Dict[str, Any]:
        """Run healing agent."""
        try:
            import healing_agent
            return {"success": True, "message": "Healing agent not fully integrated yet"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton
_core_instance: Optional[CoreEngines] = None

def get_core() -> CoreEngines:
    """Get or create core engines instance."""
    global _core_instance
    if _core_instance is None:
        _core_instance = CoreEngines()
    return _core_instance
