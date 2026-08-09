#!/usr/bin/env python3
"""
NEXUS - Rich CLI Interface

Enhanced terminal experience with colors, panels, and live updates.
"""

import os
import sys
from typing import Optional
from datetime import datetime

# Add nexus to path
NEXUS_PATH = os.path.dirname(os.path.abspath(__file__))
if NEXUS_PATH not in sys.path:
    sys.path.insert(0, NEXUS_PATH)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    from prompt_toolkit import prompt
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
except ImportError:
    print("Rich/prompt-toolkit not installed. Run: pip install rich prompt-toolkit")
    sys.exit(1)

from config import CONFIG
from router import get_router, Intent
from memory import get_memory
from engines.ollama import get_ollama
from engines.core import get_core
from tools.shell import get_shell


console = Console()


def print_banner():
    """Print NEXUS banner."""
    banner = """
    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
    ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
    ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    """
    console.print(banner, style="bold cyan")
    console.print("      Axiom Inversion Edition — Sovereign AI Gateway", style="bold magenta")
    console.print("      λ LOVE  α ABUNDANCE  σ SAFETY  γ GROWTH", style="dim")
    console.print()


def print_status():
    """Print system status table."""
    core = get_core()
    ollama = get_ollama()
    memory = get_memory()
    
    status = core.get_system_status()
    mem_stats = memory.stats()
    
    table = Table(title="System Status", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("CPU", f"{status['cpu_percent']:.1f}%")
    table.add_row("Memory", f"{status['memory_percent']:.1f}%")
    table.add_row("Python Procs", str(status['python_processes']))
    table.add_row("Ollama", "✅" if ollama.is_available() else "❌")
    table.add_row("Models", str(len(ollama.list_models())))
    table.add_row("Memory", f"{mem_stats.get('total_entries', 0)} entries")
    
    console.print(table)
    console.print()


def print_help():
    """Print help panel."""
    help_text = """
## Commands

| Command | Description |
|---------|-------------|
| `exit` | Quit NEXUS |
| `help` | Show this help |
| `status` | Show system status |
| `voice on/off` | Toggle voice input |
| `memory` | Show memory stats |
| `clear` | Clear screen |
| `models` | List Ollama models |
| `vdr` | Run Ouroboros VDR check |

## Intent Types

- **code** - Code generation, debugging
- **build** - Create new projects
- **research** - Information lookup
- **system** - Status checks
- **deploy** - Deployment
- **command** - Shell execution

Just speak naturally - NEXUS will figure out what you need.
"""
    console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))


class NexusCLI:
    """Enhanced CLI interface for NEXUS."""
    
    def __init__(self):
        self.router = get_router(use_llm=True)
        self.memory = get_memory()
        self.ollama = get_ollama()
        self.core = get_core()
        self.shell = get_shell()
        self.voice_engine = None
        self.voice_enabled = False
        self.history_file = os.path.expanduser("~/.nexus_history")
        
    def initialize(self):
        """Initialize components."""
        with console.status("[bold green]Initializing NEXUS..."):
            self.memory.initialize()
        
        console.print("✅ NEXUS initialized", style="green")
        
    def enable_voice(self) -> bool:
        """Enable voice input."""
        try:
            from voice import VoiceEngine
            with console.status("[bold blue]Loading voice model..."):
                self.voice_engine = VoiceEngine()
                if self.voice_engine.load_model():
                    self.voice_enabled = True
                    console.print("🎤 Voice enabled", style="green")
                    return True
        except Exception as e:
            console.print(f"⚠️  Voice not available: {e}", style="yellow")
        return False
    
    def process(self, user_input: str) -> str:
        """Process user input."""
        # Classify intent
        intent_result = self.router.classify(user_input)
        engine = self.router.route(intent_result)
        
        # Display intent
        intent_color = {
            Intent.CODE: "blue",
            Intent.BUILD: "magenta",
            Intent.SYSTEM: "cyan",
            Intent.COMMAND: "yellow",
            Intent.RESEARCH: "green"
        }.get(intent_result.intent, "white")
        
        console.print(
            f"[dim]Intent: {intent_result.intent.value} ({intent_result.confidence:.0%}) → {engine}[/dim]"
        )
        
        # Save to memory
        self.memory.add(user_input, entry_type="user_input")
        
        # Execute based on intent
        response = self._execute(user_input, intent_result, engine)
        
        # Save response
        self.memory.add(response, entry_type="assistant_response")
        
        return response
    
    def _execute(self, user_input: str, intent_result, engine: str) -> str:
        """Execute based on intent."""
        intent = intent_result.intent
        
        if intent == Intent.SYSTEM:
            return self._handle_system(user_input)
        elif intent == Intent.COMMAND:
            return self._handle_command(user_input)
        elif intent == Intent.MEMORY:
            return self._handle_memory(user_input)
        else:
            return self._handle_chat(user_input)
    
    def _handle_system(self, user_input: str) -> str:
        """Handle system requests."""
        lower = user_input.lower()
        
        if 'vdr' in lower or 'ouroboros' in lower:
            with console.status("[bold cyan]Running Ouroboros..."):
                result = self.core.run_ouroboros()
            if result.get('success'):
                return f"VDR: {result['vdr']:.2f} → {result['verdict']}"
            return f"Error: {result.get('error')}"
        
        status = self.core.get_system_status()
        return f"CPU: {status['cpu_percent']:.1f}%, Memory: {status['memory_percent']:.1f}%"
    
    def _handle_command(self, user_input: str) -> str:
        """Handle shell commands."""
        command = user_input
        for prefix in ['run ', 'execute ', 'do ']:
            if command.lower().startswith(prefix):
                command = user_input[len(prefix):]
                break
        
        result = self.shell.execute(command, require_confirmation=False)
        
        if result.success:
            return result.stdout.strip() or "(no output)"
        return f"Error: {result.stderr}"
    
    def _handle_memory(self, user_input: str) -> str:
        """Handle memory queries."""
        results = self.memory.search(user_input, n_results=3)
        if results:
            return "\n".join([f"• {r['content'][:80]}..." for r in results])
        return "No relevant memories found."
    
    def _handle_chat(self, user_input: str) -> str:
        """Handle general chat."""
        context = self.memory.get_context()
        
        with console.status("[bold blue]Thinking..."):
            response = self.ollama.chat(
                prompt=user_input,
                model=CONFIG.ollama.default_model,
                system=f"You are NEXUS, a helpful AI assistant. Context:\n{context}"
            )
        
        return response.content
    
    def run(self):
        """Main CLI loop."""
        print_banner()
        self.initialize()
        print_status()
        
        console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]\n")
        
        history = FileHistory(self.history_file)
        
        while True:
            try:
                # Get input
                user_input = prompt(
                    "You: ",
                    history=history,
                    auto_suggest=AutoSuggestFromHistory()
                ).strip()
                
                if not user_input:
                    continue
                
                # Handle built-in commands
                if user_input.lower() == 'exit':
                    console.print("👋 Goodbye!", style="cyan")
                    break
                elif user_input.lower() == 'help':
                    print_help()
                    continue
                elif user_input.lower() == 'status':
                    print_status()
                    continue
                elif user_input.lower() == 'clear':
                    console.clear()
                    print_banner()
                    continue
                elif user_input.lower() == 'models':
                    models = self.ollama.list_models()
                    console.print(f"Models: {', '.join(models)}")
                    continue
                elif user_input.lower() == 'vdr':
                    response = self.process("check vdr status")
                    console.print(Panel(response, title="🐍 Ouroboros", border_style="green"))
                    continue
                elif user_input.lower() == 'voice on':
                    self.enable_voice()
                    continue
                elif user_input.lower() == 'voice off':
                    self.voice_enabled = False
                    console.print("🔇 Voice disabled")
                    continue
                
                # Process input
                response = self.process(user_input)
                
                # Display response
                console.print()
                console.print(Panel(
                    Markdown(response) if len(response) > 100 else response,
                    title="🌀 NEXUS",
                    border_style="cyan"
                ))
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n\n👋 Goodbye!", style="cyan")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


def main():
    """Main entry point."""
    cli = NexusCLI()
    cli.run()


if __name__ == "__main__":
    main()
