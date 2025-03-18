#!/usr/bin/env python3
"""Management script for emailfilter project."""

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
logger = logging.getLogger("emailfilter")
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

def train_model():
    """Run the full training flow."""
    try:
        # Download new training data
        console.rule("[bold blue]Downloading Training Data")
        run_command(
            "python -m emailfilter.training.download_data "
            "--config config/config.yaml "
            "--output-dir data/emails "
            "--max-emails 1000"
        )
        
        # Train model
        console.rule("[bold blue]Training Model")
        run_command(
            "python -m emailfilter.training.cli start "
            "--data-dir data/emails "
            "--output-dir models/email-classifier-new "
            "--model microsoft/phi-2 "
            "--device mps "
            "--epochs 5 "
            "--batch-size 4 "
            "--learning-rate 2e-4"
        )
        
        # Move new model to final location
        if (Path("models/email-classifier-new/final").exists()):
            if (Path("models/email-classifier-v2/final").exists()):
                run_command("rm -rf models/email-classifier-v2/final.bak")
                run_command("mv models/email-classifier-v2/final models/email-classifier-v2/final.bak")
            run_command("mv models/email-classifier-new/final models/email-classifier-v2/final")
            run_command("rm -rf models/email-classifier-new")
            logger.info("✅ Training completed successfully!")
        else:
            logger.error("❌ Training failed - model directory not found")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Training failed: {e}")
        if e.output:
            logger.error(e.output)

def test_model():
    """Test the model on the test dataset."""
    try:
        console.rule("[bold blue]Testing Model")
        run_command(
            "python -m emailfilter.training.cli evaluate "
            "--model-dir models/email-classifier-v2/final "
            "--test-dir data/emails "
            "--device mps"
        )
        logger.info("✅ Testing completed!")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Testing failed: {e}")
        if e.output:
            logger.error(e.output)

def build_docker():
    """Build the Docker image."""
    try:
        console.rule("[bold blue]Building Docker Image")
        # Build for both ARM and x86
        run_command(
            "docker buildx build "
            "--platform linux/amd64/v2,linux/arm64 "
            "-t tomfagerland520/emailfilter:latest "
            "."
        )
        logger.info("✅ Docker build completed!")
        
        # Ask if user wants to push
        if questionary.confirm("Do you want to push the image to Docker Hub?").ask():
            run_command("docker push tomfagerland520/emailfilter:latest")
            logger.info("✅ Docker push completed!")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Docker build failed: {e}")
        if e.output:
            logger.error(e.output)

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