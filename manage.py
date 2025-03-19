#!/usr/bin/env python3
"""Management script for Mailmind."""

import os
import sys
import logging
import subprocess
from pathlib import Path

import questionary
from rich.console import Console
from rich.logging import RichHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("mailmind")
console = Console()

def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command.
    
    Args:
        cmd: Command to run
        check: Whether to check return code
        
    Returns:
        CompletedProcess instance
    """
    logger.debug(f"Running command: {cmd}")
    return subprocess.run(
        cmd,
        shell=True,
        check=check,
        text=True
    )

def train_model() -> None:
    """Train a new model."""
    print("\nTraining new model...")
    subprocess.run([sys.executable, "-m", "mailmind.training.cli", "train", "--help"])


def test_model() -> None:
    """Test the current model."""
    print("\nTesting current model...")
    subprocess.run([sys.executable, "-m", "mailmind.training.cli", "evaluate", "--help"])


def build_docker() -> None:
    """Build Docker image."""
    print("\nBuilding Docker image...")
    subprocess.run(["docker", "build", "-t", "mailmind", "."])


def main():
    """Main entry point."""
    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Train new model",
                "Test current model",
                "Build Docker image",
                "Quit"
            ]
        ).ask()
        
        if choice == "Train new model":
            train_model()
        elif choice == "Test current model":
            test_model()
        elif choice == "Build Docker image":
            build_docker()
        else:
            break
        
        # Add spacing between operations
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
        sys.exit(0) 