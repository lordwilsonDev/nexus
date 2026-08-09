"""
NEXUS - Shell Tool

Sandboxed shell command execution.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

# Commands that are always blocked
BLOCKED_COMMANDS = [
    'rm -rf /',
    'rm -rf ~',
    'rm -rf *',
    ':(){:|:&};:',  # Fork bomb
    'dd if=/dev/zero',
    'mkfs',
    'chmod -R 777 /',
]

# Commands that require confirmation
DANGEROUS_PATTERNS = [
    'rm -rf',
    'rm -r',
    'sudo',
    'chmod',
    'chown',
    'kill -9',
    'pkill',
    'shutdown',
    'reboot',
]


@dataclass
class ShellResult:
    """Result of shell command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    success: bool


class ShellTool:
    """
    Safe shell command execution.
    """
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or os.getcwd()
        self.history: List[ShellResult] = []
        
    def is_blocked(self, command: str) -> bool:
        """Check if command is blocked."""
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return True
        return False
    
    def is_dangerous(self, command: str) -> bool:
        """Check if command requires confirmation."""
        cmd_lower = command.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return True
        return False
    
    def execute(
        self, 
        command: str, 
        timeout: int = 60,
        require_confirmation: bool = True
    ) -> ShellResult:
        """Execute a shell command."""
        
        # Check if blocked
        if self.is_blocked(command):
            result = ShellResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr="Command blocked for safety",
                success=False
            )
            return result
        
        # Check if dangerous (caller should confirm)
        if require_confirmation and self.is_dangerous(command):
            result = ShellResult(
                command=command,
                returncode=-2,
                stdout="",
                stderr="CONFIRMATION_REQUIRED: This command may be dangerous",
                success=False
            )
            return result
        
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result = ShellResult(
                command=command,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                success=proc.returncode == 0
            )
            
        except subprocess.TimeoutExpired:
            result = ShellResult(
                command=command,
                returncode=-3,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                success=False
            )
            
        except Exception as e:
            result = ShellResult(
                command=command,
                returncode=-4,
                stdout="",
                stderr=str(e),
                success=False
            )
        
        self.history.append(result)
        return result
    
    def cd(self, path: str) -> bool:
        """Change working directory."""
        new_path = os.path.abspath(os.path.join(self.working_dir, path))
        if os.path.isdir(new_path):
            self.working_dir = new_path
            return True
        return False
    
    def pwd(self) -> str:
        """Get current working directory."""
        return self.working_dir


# Singleton
_shell_instance: Optional[ShellTool] = None

def get_shell() -> ShellTool:
    """Get or create shell tool instance."""
    global _shell_instance
    if _shell_instance is None:
        _shell_instance = ShellTool()
    return _shell_instance
