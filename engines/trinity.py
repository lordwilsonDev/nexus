#!/usr/bin/env python3
"""
NEXUS Engine Connector for TRINITY
Bridges the Gateway to the Tiered Model Router.
"""

import sys
from pathlib import Path

# Add trinity to path. APPEND, never insert(0): ~/.trinity also ships a
# router.py, and a leading path entry would shadow this repo's own router.py
# (order-dependent ImportError: cannot import name 'Intent' from 'router').
# Repo-local modules must always win; ~/.trinity's non-colliding modules
# (context_daemon) still resolve.
TRINITY_PATH = Path.home() / ".trinity"
if str(TRINITY_PATH) not in sys.path:
    sys.path.append(str(TRINITY_PATH))

try:
    from context_daemon import get_context

    from router import TieredRouter  # type: ignore[attr-defined]
    _TRINITY_IMPORT_OK = True
except ImportError:
    # Safe fallbacks — record that the real router did NOT load so
    # is_available() reports honestly instead of claiming a working router.
    _TRINITY_IMPORT_OK = False
    def get_context(): return {}
    class TieredRouter:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs): pass
        async def chat(self, prompt, **kwargs):
            return type('obj', (object,), {'content': "Trinity Router not found."})

class TrinityEngine:
    """Connector class for the Trinity tiered router."""
    
    def __init__(self):
        self.router = TieredRouter()
        self._is_available = TRINITY_PATH.exists() and _TRINITY_IMPORT_OK
        
    def is_available(self) -> bool:
        return self._is_available
    
    def chat(self, prompt: str, tier: str = "cortex", **kwargs) -> str:
        """Forward chat to the Trinity tiered router."""
        import asyncio
        
        # Determine tier from string
        try:
            from router import ModelTier  # type: ignore[attr-defined]
            model_tier = ModelTier.DEEP_MIND if tier == "deep_mind" else ModelTier.CORTEX
        except ImportError:
            model_tier = None
            
        # Get local hardware context
        context = get_context()
        
        # Run async chat in sync wrapper for Nexus
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self.router.chat(
                    prompt=prompt,
                    tier=model_tier,
                    context=context,
                    **kwargs
                )
            )
            return response.content
        finally:
            loop.close()

def get_trinity():
    return TrinityEngine()
