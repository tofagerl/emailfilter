#!/usr/bin/env python3
"""
Mailmind - A Python application for intelligent email management.

This is a simple entry point that demonstrates the email categorization.
"""

import argparse
import logging
import sys
from pathlib import Path

from mailmind.inference.cli import main as inference_main
from mailmind.training.cli import main as training_main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Mailmind - Email Categorization")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--mode",
        choices=["inference", "training"],
        default="inference",
        help="Operation mode"
    )
    args = parser.parse_args()
    
    # Check if config file exists
    if not Path(args.config).exists():
        print(f"\nError: Configuration file not found at {args.config}")
        print("\nPlease create a config.yaml file with your email accounts:")
        print("accounts:")
        print("  - name: \"Your Account\"")
        print("    email: \"your.email@example.com\"")
        print("    password: \"your_password\"")
        print("    imap_server: \"imap.example.com\"")
        print("    categories:")
        print("      - name: \"SPAM\"")
        print("        description: \"Unwanted or malicious emails\"")
        print("        folder: \"Spam\"")
        sys.exit(1)
    
    try:
        if args.mode == "inference":
            inference_main(args.config)
        else:
            training_main(args.config)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()



