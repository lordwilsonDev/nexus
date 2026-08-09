"""
NEXUS - Vector Memory Layer

Persistent memory using ChromaDB for semantic search.
Stores conversations, context, and episodic memory.
"""

import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Lazy import ChromaDB
_chroma: Any = None


def _lazy_import_chroma():
    """Lazy import ChromaDB."""
    global _chroma
    if _chroma is None:
        try:
            import chromadb
            _chroma = chromadb
        except ImportError:
            print("⚠️  ChromaDB not installed. Run: pip install chromadb")
            return False
    return True


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    content: str
    type: str  # "conversation", "context", "episodic", "project"
    timestamp: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class MemoryLayer:
    """
    Persistent vector memory using ChromaDB.
    """
    
    def __init__(
        self, 
        persist_dir: str = "data/chromadb",
        collection_name: str = "nexus_memory"
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.client: Any = None
        self.collection: Any = None
        self._session_memory: List[Dict] = []
        
    def initialize(self) -> bool:
        """Initialize ChromaDB connection."""
        if not _lazy_import_chroma():
            return False
            
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            
            self.client = _chroma.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            print(f"✅ Memory initialized ({self.collection.count()} entries)")
            return True
            
        except Exception as e:
            print(f"❌ Memory initialization failed: {e}")
            return False
    
    def add(
        self,
        content: str,
        entry_type: str = "conversation",
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a memory entry."""
        if not self.collection:
            if not self.initialize():
                return ""
        
        entry_id = f"{entry_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        timestamp = datetime.now().isoformat()
        
        meta = {
            "type": entry_type,
            "timestamp": timestamp,
            **(metadata or {})
        }
        
        try:
            self.collection.add(
                ids=[entry_id],
                documents=[content],
                metadatas=[meta]
            )
            
            # Also add to session memory
            self._session_memory.append({
                "id": entry_id,
                "content": content,
                "type": entry_type,
                "timestamp": timestamp
            })
            
            return entry_id
            
        except Exception as e:
            print(f"Memory add error: {e}")
            return ""
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        entry_type: Optional[str] = None
    ) -> List[Dict]:
        """Search memory by semantic similarity."""
        if not self.collection:
            if not self.initialize():
                return []
        
        try:
            where_filter = {"type": entry_type} if entry_type else None
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            entries = []
            for i, doc in enumerate(results.get('documents', [[]])[0]):
                entry = {
                    "id": results['ids'][0][i] if results.get('ids') else None,
                    "content": doc,
                    "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                    "distance": results['distances'][0][i] if results.get('distances') else None
                }
                entries.append(entry)
                
            return entries
            
        except Exception as e:
            print(f"Memory search error: {e}")
            return []
    
    def get_session_memory(self, limit: int = 10) -> List[Dict]:
        """Get recent session memory."""
        return self._session_memory[-limit:]
    
    def get_context(self) -> str:
        """Get formatted context from session memory for LLM."""
        if not self._session_memory:
            return ""
            
        context_parts = []
        for entry in self._session_memory[-5:]:  # Last 5 entries
            role = "User" if entry['type'] == 'user_input' else "NEXUS"
            context_parts.append(f"{role}: {entry['content']}")
            
        return "\n".join(context_parts)
    
    def save_conversation(self, user_input: str, response: str):
        """Save a conversation turn."""
        self.add(user_input, entry_type="user_input")
        self.add(response, entry_type="assistant_response")
    
    def add_project_context(self, project_name: str, description: str):
        """Add project context for future reference."""
        self.add(
            f"Project: {project_name}\n{description}",
            entry_type="project",
            metadata={"project_name": project_name}
        )
    
    def add_episodic(self, event: str, outcome: str):
        """Add episodic memory (what happened and result)."""
        self.add(
            f"Event: {event}\nOutcome: {outcome}",
            entry_type="episodic",
            metadata={"event": event}
        )
    
    def clear_session(self):
        """Clear session memory (not persistent memory)."""
        self._session_memory = []
    
    def stats(self) -> Dict:
        """Get memory statistics."""
        if not self.collection:
            return {"initialized": False}
            
        return {
            "initialized": True,
            "total_entries": self.collection.count(),
            "session_entries": len(self._session_memory),
            "persist_dir": self.persist_dir
        }


# Global instance
_memory_instance: Optional[MemoryLayer] = None

def get_memory(persist_dir: str = "data/chromadb") -> MemoryLayer:
    """Get or create memory layer instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryLayer(persist_dir=persist_dir)
    return _memory_instance


# Test
if __name__ == "__main__":
    print("🧠 NEXUS Memory Test")
    print("=" * 40)
    
    memory = MemoryLayer(persist_dir="data/test_chromadb")
    
    if memory.initialize():
        # Add some memories
        memory.add("How do I deploy to production?", entry_type="user_input")
        memory.add("Use the deploy command with --prod flag", entry_type="assistant_response")
        memory.add_project_context("NEXUS", "Universal agent gateway")
        
        # Search
        results = memory.search("deploy production")
        print("\nSearch results for 'deploy production':")
        for r in results:
            print(f"  - {r['content'][:50]}...")
        
        # Stats
        print(f"\nStats: {memory.stats()}")
