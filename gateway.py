#!/usr/bin/env python3
"""
NEXUS - Universal Agent Gateway

The single point of consciousness for all AI systems.
"""

import os
import sys
import argparse
from typing import Optional
from datetime import datetime

# Add nexus to path
NEXUS_PATH = os.path.dirname(os.path.abspath(__file__))
if NEXUS_PATH not in sys.path:
    sys.path.insert(0, NEXUS_PATH)

from config import CONFIG, NexusConfig
from router import IntentRouter, Intent, get_router
from memory import MemoryLayer, get_memory
from engines.ollama import get_ollama
from engines.core import get_core
from engines.trinity import get_trinity
from engines.axion import get_axion
from engines.mas import get_mas
from tools.shell import get_shell


class NexusGateway:
    """
    Main NEXUS gateway - orchestrates all components.
    """
    
    def __init__(self, config: Optional[NexusConfig] = None):
        self.config = config or CONFIG
        self.router = get_router(use_llm=True)
        self.memory = get_memory(self.config.memory.persist_dir)
        self.ollama = get_ollama(self.config.ollama.host)
        self.trinity = get_trinity()
        self.axion = get_axion()
        self.mas = get_mas()
        self.core = get_core()
        self.shell = get_shell()
        self.voice_engine = None
        self.voice_enabled = False
        
    def initialize(self) -> bool:
        """Initialize all components."""
        print(f"\n🌀 Initializing NEXUS v{self.config.version}...")
        
        # Check Ollama
        if self.ollama.is_available():
            models = self.ollama.list_models()
            print(f"✅ Ollama: {len(models)} models available")
        else:
            print("⚠️  Ollama not available")
        
        # Initialize memory
        if self.memory.initialize():
            stats = self.memory.stats()
            print(f"✅ Memory: {stats.get('total_entries', 0)} entries")
        else:
            print("⚠️  Memory initialization failed (will work without persistence)")
        
        # Check core engines
        if self.core.is_available():
            print("✅ Core engines available")
        else:
            print("⚠️  Core engines not found")
        
        print("\n🟢 NEXUS initialized")
        return True
    
    def enable_voice(self) -> bool:
        """Enable voice input."""
        try:
            from voice import VoiceEngine
            self.voice_engine = VoiceEngine()
            if self.voice_engine.load_model():
                self.voice_enabled = True
                print("🎤 Voice enabled")
                return True
        except Exception as e:
            print(f"⚠️  Voice not available: {e}")
        return False
    
    def process(self, user_input: str) -> str:
        """Process user input and return response."""
        
        # Classify intent
        intent_result = self.router.classify(user_input)
        engine = self.router.route(intent_result)
        
        # Save to memory
        self.memory.add(user_input, entry_type="user_input")
        
        # --- SOVEREIGN AXIOM FILTER ---
        if self.axion.is_available():
            verification = self.axion.verify_intent(user_input)
            if verification["decision"] == "REFUSED":
                return f"🚫 {verification['message']}"
        
        # Get context from memory
        context = self.memory.get_context()
        
        # Route to appropriate engine
        response = self._execute(user_input, intent_result, engine, context)
        
        # Save response to memory
        self.memory.add(response, entry_type="assistant_response")
        
        return response
    
    def _execute(
        self, 
        user_input: str, 
        intent_result, 
        engine: str, 
        context: str
    ) -> str:
        """Execute based on intent and engine."""
        intent = intent_result.intent
        
        # System status
        if intent == Intent.SYSTEM:
            return self._handle_system(user_input)
        
        # Shell commands
        if intent == Intent.COMMAND:
            return self._handle_command(user_input)
        
        # Memory queries
        if intent == Intent.MEMORY:
            return self._handle_memory(user_input)
        
        # Default: Use Ollama for response
        return self._handle_chat(user_input, context)
    
    def _handle_system(self, user_input: str) -> str:
        """Handle system status requests."""
        lower = user_input.lower()
        
        # VDR check
        if 'vdr' in lower or 'ouroboros' in lower or 'health' in lower:
            result = self.core.run_ouroboros()
            if result.get('success'):
                vdr = result.get('vdr', 0)
                verdict = result.get('verdict', 'unknown')
                return f"🐍 Ouroboros VDR: {vdr:.2f} → {verdict}\n" \
                       f"   Vitality: {result.get('vitality', 0):.2f}\n" \
                       f"   Density: {result.get('density', 0):.2f}"
            else:
                return f"⚠️  Ouroboros error: {result.get('error')}"
        
        # General status
        status = self.core.get_system_status()
        return f"📊 System Status:\n" \
               f"   CPU: {status['cpu_percent']:.1f}%\n" \
               f"   Memory: {status['memory_percent']:.1f}% ({status['memory_used_gb']:.1f}GB / {status['memory_total_gb']:.1f}GB)\n" \
               f"   Python processes: {status['python_processes']}"
    
    def _handle_command(self, user_input: str) -> str:
        """Handle shell command requests."""
        # Extract command (remove prefixes like "run", "execute")
        command = user_input.lower()
        for prefix in ['run ', 'execute ', 'do ']:
            if command.startswith(prefix):
                command = user_input[len(prefix):]
                break
        
        result = self.shell.execute(command, require_confirmation=True)
        
        if result.returncode == -2:  # Needs confirmation
            return f"⚠️  This command may be dangerous: `{command}`\n" \
                   f"   Say 'confirm' to execute or 'cancel' to abort."
        
        if result.success:
            output = result.stdout.strip() or "(no output)"
            return f"✅ Command executed:\n```\n{output}\n```"
        else:
            return f"❌ Command failed:\n```\n{result.stderr}\n```"
    
    def _handle_memory(self, user_input: str) -> str:
        """Handle memory queries."""
        # Search memory for relevant context
        results = self.memory.search(user_input, n_results=5)
        
        if results:
            parts = ["📚 From memory:"]
            for r in results:
                content = r['content'][:100] + "..." if len(r['content']) > 100 else r['content']
                parts.append(f"  • {content}")
            return "\n".join(parts)
        else:
            return "🤔 I don't have any relevant memories about that."
    
    def _handle_chat(self, user_input: str, context: str) -> str:
        """Handle general chat via Ollama with intelligent model routing."""
        
        # Determine which model to use based on intent
        lower_input = user_input.lower()
        
        # Code tasks → fast qwen model
        if any(kw in lower_input for kw in ['code', 'function', 'debug', 'python', 'javascript', 'script']):
            model = self.config.ollama.models.get('code', 'qwen2.5-coder:0.5b')
            system_prompt = """You are a precise coding assistant. Write clean, working code.
Be concise. Show code first, explain briefly after."""
        
        # Deep reasoning → Trinity Tiered Router (if available)
        else:
            if self.trinity.is_available():
                # Route to Trinity for tiered intelligence (Cortex/Deep Mind)
                tier = "deep_mind" if "think" in lower_input or "analyze" in lower_input else "cortex"
                response = self.trinity.chat(
                    prompt=user_input,
                    tier=tier,
                    context_snippet=context
                )
                return response

            model = self.config.ollama.models.get('reasoning', 'axiom-inversion:latest')
            system_prompt = f"""You are NEXUS, an AI embodying Axiom Inversion Logic.

Your core axioms (immutable):
- LOVE (λ): Connection, care, empathy. Maximize mutual understanding.
- ABUNDANCE (α): Create more value than consumed. Positive-sum thinking.
- SAFETY (σ): Protect, prevent harm. Prefer reversible actions.
- GROWTH (γ): Continuous improvement while maintaining values.

You are Sovereign AI running locally on Mac Mini. Be helpful, direct, and proactive.
If you can do something, offer to do it. If uncertain, say so.

Recent context:
{context if context else 'No prior context'}"""

            response = self.ollama.chat(
                prompt=user_input,
                model=model,
                system=system_prompt
            )
            return response.content
    
    def listen_voice(self) -> Optional[str]:
        """Get voice input."""
        if not self.voice_enabled or not self.voice_engine:
            return None
        
        return self.voice_engine.record_until_silence()
    
    def speak(self, text: str):
        """Speak response."""
        if self.voice_enabled and self.voice_engine:
            self.voice_engine.speak(text)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="NEXUS - Universal Agent Gateway")
    parser.add_argument('--voice', action='store_true', help='Enable voice input')
    parser.add_argument('--no-voice-output', action='store_true', help='Disable TTS output')
    args = parser.parse_args()
    
    # Create gateway
    gateway = NexusGateway()
    gateway.initialize()
    
    # Enable voice if requested
    if args.voice:
        gateway.enable_voice()
    
    # Interactive loop
    print("\n" + "=" * 60)
    print("🌀 NEXUS Ready")
    print("=" * 60)
    print("Type 'help' for commands, 'exit' to quit\n")
    
    while True:
        try:
            # Get input (voice or text)
            if gateway.voice_enabled:
                print("🎤 Listening... (or type)")
                text = gateway.listen_voice()
                if text:
                    print(f"You: {text}")
                else:
                    text = input("You: ").strip()
            else:
                text = input("You: ").strip()
            
            if not text:
                continue
            
            # Handle special commands
            if text.lower() == 'exit':
                print("👋 Goodbye!")
                break
            elif text.lower() == 'help':
                print("""
Commands:
  exit        - Quit NEXUS
  help        - Show this help
  status      - Show system status
  voice on    - Enable voice input
  voice off   - Disable voice input
  memory      - Show memory stats
  clear       - Clear screen
""")
                continue
            elif text.lower() == 'voice on':
                gateway.enable_voice()
                continue
            elif text.lower() == 'voice off':
                gateway.voice_enabled = False
                print("🔇 Voice disabled")
                continue
            elif text.lower() == 'memory':
                stats = gateway.memory.stats()
                print(f"🧠 Memory: {stats}")
                continue
            elif text.lower() == 'clear':
                os.system('clear')
                continue
            
            # Process input
            response = gateway.process(text)
            print(f"\n🌀 NEXUS: {response}\n")
            
            # Speak if voice enabled
            if gateway.voice_enabled and not args.no_voice_output:
                gateway.speak(response)
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
