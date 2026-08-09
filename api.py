#!/usr/bin/env python3
"""
NEXUS - HTTP API Server

FastAPI server for external access to NEXUS.
"""

import os
import sys
from datetime import datetime
from typing import Optional

# Add nexus to path
NEXUS_PATH = os.path.dirname(os.path.abspath(__file__))
if NEXUS_PATH not in sys.path:
    sys.path.insert(0, NEXUS_PATH)

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

from config import CONFIG
from engines.core import get_core
from engines.ollama import get_ollama
from memory import get_memory
from router import get_router
from tools.shell import get_shell

# FastAPI app
app = FastAPI(
    title="NEXUS API",
    description="Universal Agent Gateway API",
    version=CONFIG.version
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    engine: str
    timestamp: str


class CommandRequest(BaseModel):
    command: str
    confirm: bool = False


class CommandResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None


class SystemStatus(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    python_processes: int
    ollama_available: bool
    ollama_models: list
    memory_entries: int


# Initialize components
router = get_router()
memory = get_memory()
ollama = get_ollama()
core = get_core()
shell = get_shell()

# Initialize memory on startup
@app.on_event("startup")
async def startup():
    memory.initialize()


@app.get("/")
async def root():
    """API root."""
    return {
        "name": "NEXUS API",
        "version": CONFIG.version,
        "status": "running"
    }


@app.get("/status", response_model=SystemStatus)
async def status():
    """Get system status."""
    sys_status = core.get_system_status()
    mem_stats = memory.stats()
    
    return SystemStatus(
        cpu_percent=sys_status['cpu_percent'],
        memory_percent=sys_status['memory_percent'],
        memory_used_gb=sys_status['memory_used_gb'],
        python_processes=sys_status['python_processes'],
        ollama_available=ollama.is_available(),
        ollama_models=ollama.list_models(),
        memory_entries=mem_stats.get('total_entries', 0)
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message."""
    # Classify intent
    intent_result = router.classify(request.message)
    engine = router.route(intent_result)
    
    # Save to memory
    memory.add(request.message, entry_type="user_input")
    
    # Get context
    context = request.context or memory.get_context()
    
    # Generate response
    system_prompt = f"""You are NEXUS, a powerful AI assistant.
Context: {context}"""

    response = ollama.chat(
        prompt=request.message,
        model=CONFIG.ollama.default_model,
        system=system_prompt
    )
    
    # Save response
    memory.add(response.content, entry_type="assistant_response")
    
    return ChatResponse(
        response=response.content,
        intent=intent_result.intent.value,
        engine=engine,
        timestamp=datetime.now().isoformat()
    )


@app.post("/command", response_model=CommandResponse)
async def command(request: CommandRequest):
    """Execute a shell command."""
    result = shell.execute(
        request.command, 
        require_confirmation=not request.confirm
    )
    
    if result.returncode == -2:
        raise HTTPException(
            status_code=400,
            detail="Command requires confirmation. Set confirm=true to execute."
        )
    
    return CommandResponse(
        success=result.success,
        output=result.stdout,
        error=result.stderr if not result.success else None
    )


@app.get("/vdr")
async def vdr():
    """Get Ouroboros VDR."""
    result = core.run_ouroboros()
    return result


@app.get("/memory/search")
async def memory_search(query: str, limit: int = 5):
    """Search memory."""
    results = memory.search(query, n_results=limit)
    return {"results": results}


@app.get("/models")
async def models():
    """List available Ollama models."""
    return {"models": ollama.list_models()}


def main():
    """Run the API server."""
    print("🌀 Starting NEXUS API Server...")
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
