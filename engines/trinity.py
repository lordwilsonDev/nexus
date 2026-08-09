#!/usr/bin/env python3
"""
NEXUS Engine Connector for TRINITY
Bridges the Gateway to the Tiered Model Router.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Add trinity to path
TRINITY_PATH = Path.home() / ".trinity"
if str(TRINITY_PATH) not in sys.path:
    sys.path.insert(0, str(TRINITY_PATH))

try:
    from router import TieredRouter, ModelTier
    from context_daemon import get_context
except ImportError:
    # Safe fallbacks
    def get_context(): return {}
    class TieredRouter:
        def __init__(self, *args, **kwargs): pass
        async def chat(self, prompt, **kwargs):
            return type('obj', (object,), {'content': "Trinity Router not found."})

class TrinityEngine:
    """Connector class for the Trinity tiered router."""
    
    def __init__(self):
        self.router = TieredRouter()
        self._is_available = TRINITY_PATH.exists()
        
    def is_available(self) -> bool:
        return self._is_available
    
    def chat(self, prompt: str, tier: str = "cortex", **kwargs) -> str:
        """Forward chat to the Trinity tiered router."""
        import asyncio
        
        # Determine tier from string
        try:
            from router import ModelTier
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
