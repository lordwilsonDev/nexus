"""
NEXUS - Voice Input/Output

Handles speech-to-text (Whisper) and text-to-speech.
Includes wake word detection and continuous listening.
"""

import os
import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

# Lazy imports to handle missing dependencies gracefully
_whisper: Any = None
_sounddevice: Any = None
_numpy: Any = None


def _lazy_imports():
    """Lazy import audio dependencies."""
    global _whisper, _sounddevice, _numpy
    if _whisper is None:
        try:
            import numpy as np
            import sounddevice as sd
            import whisper
            _whisper = whisper
            _sounddevice = sd
            _numpy = np
        except ImportError as e:
            print(f"⚠️  Voice dependencies not installed: {e}")
            print("   Run: pip install openai-whisper sounddevice numpy")
            return False
    return True


@dataclass
class VoiceConfig:
    wake_word: str = "hey nexus"
    whisper_model: str = "base"
    language: str = "en"
    sample_rate: int = 16000
    silence_threshold: float = 0.01
    silence_duration: float = 1.5  # seconds of silence to stop recording
    max_duration: float = 30.0  # max recording duration


class VoiceEngine:
    """
    Voice input/output engine using Whisper for STT.
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.model: Any = None
        self.is_listening = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._listen_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
        
    def load_model(self) -> bool:
        """Load Whisper model."""
        if not _lazy_imports():
            return False
            
        if self.model is None:
            print(f"🎤 Loading Whisper model: {self.config.whisper_model}...")
            try:
                self.model = _whisper.load_model(self.config.whisper_model)
                print("✅ Whisper model loaded")
                return True
            except Exception as e:
                print(f"❌ Failed to load Whisper: {e}")
                return False
        return True
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text."""
        if not self.load_model():
            return ""
            
        try:
            result = self.model.transcribe(
                audio_path,
                language=self.config.language,
                fp16=False  # CPU mode
            )
            return result.get("text", "").strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def transcribe_array(self, audio_array) -> str:
        """Transcribe numpy audio array to text."""
        if not self.load_model():
            return ""
            
        try:
            # Normalize audio
            audio = audio_array.flatten().astype(_numpy.float32)
            if audio.max() > 1.0:
                audio = audio / 32768.0
                
            result = self.model.transcribe(
                audio,
                language=self.config.language,
                fp16=False
            )
            return result.get("text", "").strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def record_until_silence(self) -> Optional[str]:
        """Record audio until silence is detected, then transcribe."""
        if not _lazy_imports():
            return None
            
        print("🎙️  Listening... (speak now)")
        
        audio_chunks = []
        silence_start = None
        
        def callback(indata, frames, time_info, status):
            nonlocal silence_start
            
            volume = _numpy.abs(indata).mean()
            audio_chunks.append(indata.copy())
            
            if volume < self.config.silence_threshold:
                if silence_start is None:
                    silence_start = time.time()
            else:
                silence_start = None
        
        try:
            with _sounddevice.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype='float32',
                callback=callback
            ):
                start_time = time.time()
                
                while True:
                    time.sleep(0.1)
                    
                    # Stop on silence
                    if silence_start and (time.time() - silence_start) > self.config.silence_duration:
                        break
                    
                    # Stop on max duration
                    if (time.time() - start_time) > self.config.max_duration:
                        break
                        
        except Exception as e:
            print(f"Recording error: {e}")
            return None
        
        if not audio_chunks:
            return None
            
        # Combine and transcribe
        audio = _numpy.concatenate(audio_chunks)
        print("🔄 Transcribing...")
        
        return self.transcribe_array(audio)
    
    def detect_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        return self.config.wake_word.lower() in text.lower()
    
    def remove_wake_word(self, text: str) -> str:
        """Remove wake word from text."""
        lower = text.lower()
        wake = self.config.wake_word.lower()
        
        if wake in lower:
            idx = lower.find(wake)
            text = text[:idx] + text[idx + len(wake):]
        
        return text.strip().lstrip(',').lstrip('.').strip()
    
    def start_continuous_listening(self, callback: Callable[[str], None]):
        """Start continuous listening with wake word detection."""
        if not _lazy_imports():
            return
            
        self._callback = callback
        self.is_listening = True
        
        def listen_loop():
            print(f"🎧 Listening for wake word: '{self.config.wake_word}'")
            
            while self.is_listening:
                try:
                    # Record a short segment
                    text = self.record_until_silence()
                    
                    if text and self.detect_wake_word(text):
                        # Remove wake word and process command
                        command = self.remove_wake_word(text)
                        
                        if command:
                            print(f"🎯 Command: {command}")
                            if self._callback:
                                self._callback(command)
                        else:
                            # Wake word only - listen for command
                            print("👂 Yes?")
                            command = self.record_until_silence()
                            if command and self._callback:
                                self._callback(command)
                                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Listen error: {e}")
                    time.sleep(1)
        
        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
    
    def stop_listening(self):
        """Stop continuous listening."""
        self.is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
            self._listen_thread = None
    
    def speak(self, text: str):
        """Text-to-speech using macOS say command."""
        try:
            # Use macOS native TTS
            os.system(f'say "{text}"')
        except Exception as e:
            print(f"TTS error: {e}")


# Simple one-shot dictation
def dictate() -> str:
    """Record and transcribe a single utterance."""
    engine = VoiceEngine()
    if not engine.load_model():
        return ""
    return engine.record_until_silence() or ""


# Test
if __name__ == "__main__":
    print("🎤 NEXUS Voice Test")
    print("=" * 40)
    
    engine = VoiceEngine()
    
    if not engine.load_model():
        print("Failed to load voice engine")
        sys.exit(1)
    
    print("\n👂 Say something...")
    text = engine.record_until_silence()
    
    if text:
        print(f"\n📝 You said: {text}")
        engine.speak(f"I heard: {text}")
    else:
        print("No speech detected")
