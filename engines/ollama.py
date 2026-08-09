"""
NEXUS - Ollama Engine Connector

Handles all LLM interactions through local Ollama.
"""

import json
import httpx
from typing import Optional, Dict, List, Generator
from dataclasses import dataclass


@dataclass
class OllamaResponse:
    content: str
    model: str
    done: bool
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    

class OllamaEngine:
    """Connector for local Ollama LLMs."""
    
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = httpx.Client(timeout=120.0)
        self._models_cache: Optional[List[str]] = None
        
    def list_models(self) -> List[str]:
        """List available models."""
        if self._models_cache:
            return self._models_cache
            
        try:
            response = self.client.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                self._models_cache = [m['name'] for m in data.get('models', [])]
                return self._models_cache
        except Exception as e:
            print(f"Error listing models: {e}")
        return []
    
    def chat(
        self, 
        prompt: str, 
        model: str = "phi3:latest",
        system: Optional[str] = None,
        context: Optional[List[int]] = None,
        temperature: float = 0.7
    ) -> OllamaResponse:
        """Send a chat message and get response."""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if context:
            payload["context"] = context
            
        try:
            response = self.client.post(
                f"{self.host}/api/chat",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return OllamaResponse(
                    content=data.get('message', {}).get('content', ''),
                    model=model,
                    done=True,
                    total_duration=data.get('total_duration')
                )
            else:
                return OllamaResponse(
                    content=f"Error: {response.status_code}",
                    model=model,
                    done=True
                )
                
        except Exception as e:
            return OllamaResponse(
                content=f"Error: {str(e)}",
                model=model,
                done=True
            )
    
    def stream(
        self,
        prompt: str,
        model: str = "phi3:latest",
        system: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Stream response tokens."""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        try:
            with self.client.stream(
                "POST",
                f"{self.host}/api/chat",
                json=payload
            ) as response:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        content = data.get('message', {}).get('content', '')
                        if content:
                            yield content
                        if data.get('done'):
                            break
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def embed(self, text: str, model: str = "phi3:latest") -> List[float]:
        """Get embeddings for text."""
        try:
            response = self.client.post(
                f"{self.host}/api/embeddings",
                json={"model": model, "prompt": text}
            )
            if response.status_code == 200:
                return response.json().get('embedding', [])
        except Exception as e:
            print(f"Embedding error: {e}")
        return []
    
    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = self.client.get(f"{self.host}/api/version")
            return response.status_code == 200
        except:
            return False
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()


# Singleton instance
_ollama_instance: Optional[OllamaEngine] = None

def get_ollama(host: str = "http://localhost:11434") -> OllamaEngine:
    """Get or create Ollama engine instance."""
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OllamaEngine(host)
    return _ollama_instance
