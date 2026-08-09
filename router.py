"""
NEXUS - Intent Router

Classifies user intent and routes to appropriate engine.
Uses Ollama for intelligent classification with fallback to keywords.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

from engines.ollama import get_ollama


class Intent(Enum):
    """Possible user intents."""
    CODE = "code"           # Code generation, debugging, refactoring
    BUILD = "build"         # System/project creation
    RESEARCH = "research"   # Information lookup, explanation
    SYSTEM = "system"       # System status, health checks
    DEPLOY = "deploy"       # Deployment, publishing
    META = "meta"           # Meta-system building
    CHAT = "chat"           # General conversation
    COMMAND = "command"     # Direct command execution
    MEMORY = "memory"       # Memory operations
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    extracted_params: Dict
    original_input: str


# Keyword patterns for fast detection
INTENT_PATTERNS = {
    Intent.CODE: [
        r'\b(code|function|class|debug|fix|implement|refactor|write|create.*function)\b',
        r'\b(python|javascript|typescript|swift|rust)\b',
        r'\b(bug|error|exception|traceback)\b'
    ],
    Intent.BUILD: [
        r'\b(build|create|generate|scaffold|new project|init|setup)\b',
        r'\b(app|application|service|api|website)\b'
    ],
    Intent.RESEARCH: [
        r'\b(what is|how (do|to|does)|explain|tell me|find|search|look up)\b',
        r'\b(why|when|where|who)\b.*\?',
        r'\b(documentation|docs|tutorial)\b'
    ],
    Intent.SYSTEM: [
        r'\b(status|health|running|process|memory|cpu|disk)\b',
        r'\b(check|show|list).*(running|active|status)\b',
        r'\b(ollama|docker|ray)\b'
    ],
    Intent.DEPLOY: [
        r'\b(deploy|push|release|publish|ship)\b',
        r'\b(production|staging|live)\b'
    ],
    Intent.META: [
        r'\b(meta|evolve|pattern|system builder|recursive)\b',
        r'\b(build.*system|system.*build)\b'
    ],
    Intent.COMMAND: [
        r'^(run|execute|do|make)\s+',
        r'\b(shell|terminal|command|script)\b'
    ],
    Intent.MEMORY: [
        r'\b(remember|recall|forget|what did I|history)\b',
        r'\b(yesterday|last time|before|earlier)\b'
    ]
}


class IntentRouter:
    """
    Routes user input to appropriate engine based on intent.
    """
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.ollama = get_ollama() if use_llm else None
        
    def classify(self, user_input: str) -> IntentResult:
        """Classify user intent."""
        # First try fast keyword matching
        keyword_intent, keyword_confidence = self._keyword_match(user_input)
        
        # If high confidence from keywords, use that
        if keyword_confidence > 0.8:
            return IntentResult(
                intent=keyword_intent,
                confidence=keyword_confidence,
                extracted_params=self._extract_params(user_input, keyword_intent),
                original_input=user_input
            )
        
        # Otherwise use LLM for better classification
        if self.use_llm and self.ollama and self.ollama.is_available():
            llm_intent, llm_confidence = self._llm_classify(user_input)
            
            if llm_confidence > keyword_confidence:
                return IntentResult(
                    intent=llm_intent,
                    confidence=llm_confidence,
                    extracted_params=self._extract_params(user_input, llm_intent),
                    original_input=user_input
                )
        
        # Fallback to keyword result or CHAT
        if keyword_confidence > 0.3:
            return IntentResult(
                intent=keyword_intent,
                confidence=keyword_confidence,
                extracted_params=self._extract_params(user_input, keyword_intent),
                original_input=user_input
            )
        
        return IntentResult(
            intent=Intent.CHAT,
            confidence=0.5,
            extracted_params={},
            original_input=user_input
        )
    
    def _keyword_match(self, text: str) -> Tuple[Intent, float]:
        """Match intent using keyword patterns."""
        text_lower = text.lower()
        scores = {}
        
        for intent, patterns in INTENT_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
            if score > 0:
                scores[intent] = score / len(patterns)
        
        if scores:
            best_intent = max(scores, key=lambda k: scores[k])
            return best_intent, scores[best_intent]
        
        return Intent.CHAT, 0.0
    
    def _llm_classify(self, text: str) -> Tuple[Intent, float]:
        """Use LLM for intent classification."""
        if self.ollama is None:
            return Intent.CHAT, 0.0
        system_prompt = """You are an intent classifier. Given user input, respond with ONLY one word - the intent category:
- CODE: code generation, debugging, programming
- BUILD: creating new projects, apps, systems
- RESEARCH: looking up information, explanations
- SYSTEM: checking status, health, processes
- DEPLOY: deployment, publishing
- META: meta-system building, patterns
- COMMAND: running shell commands
- MEMORY: recalling past conversations
- CHAT: general conversation

Respond with ONLY the category name, nothing else."""

        try:
            response = self.ollama.chat(
                prompt=text,
                model="qwen2.5-coder:0.5b",  # Fast model for classification
                system=system_prompt,
                temperature=0.1
            )
            
            result = response.content.strip().upper()
            
            # Map to Intent enum
            intent_map = {
                "CODE": Intent.CODE,
                "BUILD": Intent.BUILD,
                "RESEARCH": Intent.RESEARCH,
                "SYSTEM": Intent.SYSTEM,
                "DEPLOY": Intent.DEPLOY,
                "META": Intent.META,
                "COMMAND": Intent.COMMAND,
                "MEMORY": Intent.MEMORY,
                "CHAT": Intent.CHAT
            }
            
            if result in intent_map:
                return intent_map[result], 0.85
            
        except Exception as e:
            print(f"LLM classification error: {e}")
        
        return Intent.UNKNOWN, 0.0
    
    def _extract_params(self, text: str, intent: Intent) -> Dict:
        """Extract relevant parameters based on intent."""
        params = {}
        
        if intent == Intent.CODE:
            # Extract language if mentioned
            lang_match = re.search(
                r'\b(python|javascript|typescript|swift|rust|go|java)\b',
                text.lower()
            )
            if lang_match:
                params['language'] = lang_match.group(1)
        
        elif intent == Intent.BUILD:
            # Extract project type
            type_match = re.search(
                r'\b(app|api|website|service|cli|tool)\b',
                text.lower()
            )
            if type_match:
                params['project_type'] = type_match.group(1)
        
        elif intent == Intent.DEPLOY:
            # Extract target
            target_match = re.search(
                r'\b(production|staging|dev|local)\b',
                text.lower()
            )
            if target_match:
                params['target'] = target_match.group(1)
        
        return params
    
    def route(self, intent_result: IntentResult) -> str:
        """Determine which engine should handle this intent."""
        engine_map = {
            Intent.CODE: "motia",
            Intent.BUILD: "meta",
            Intent.RESEARCH: "ollama",
            Intent.SYSTEM: "core",
            Intent.DEPLOY: "core",
            Intent.META: "meta",
            Intent.COMMAND: "shell",
            Intent.MEMORY: "memory",
            Intent.CHAT: "ollama"
        }
        
        return engine_map.get(intent_result.intent, "ollama")


# Singleton instance
_router_instance: Optional[IntentRouter] = None

def get_router(use_llm: bool = True) -> IntentRouter:
    """Get or create router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntentRouter(use_llm=use_llm)
    return _router_instance


# Test
if __name__ == "__main__":
    print("🎯 NEXUS Intent Router Test")
    print("=" * 40)
    
    router = IntentRouter(use_llm=False)  # Fast mode for testing
    
    test_inputs = [
        "Write a Python function to sort a list",
        "Build me a task scheduler app",
        "What is the capital of France?",
        "Check system status",
        "Deploy to production",
        "Create a meta-system for building apps",
        "Run ls -la",
        "What did I work on yesterday?",
        "Hello, how are you?"
    ]
    
    for inp in test_inputs:
        result = router.classify(inp)
        engine = router.route(result)
        print(f"\n'{inp[:40]}...'")
        print(f"  → Intent: {result.intent.value} ({result.confidence:.0%})")
        print(f"  → Engine: {engine}")
