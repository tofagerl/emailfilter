#!/usr/bin/env python
"""Test script to demonstrate the local state system for tracking processed emails."""

import os
import json
import logging
import argparse
from datetime import datetime

from emailfilter.imap_client import EmailProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test the local state system")
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--action",
        choices=["view", "add", "clean", "reset"],
        default="view",
        help="Action to perform on the state"
    )
    parser.add_argument(
        "--account",
        type=str,
        help="Account to use for testing"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of test emails to add to the state"
    )
    return parser.parse_args()

def view_state(processor):
    """View the current state."""
    logger.info("Current state:")
    
    if not processor.processed_state:
        logger.info("  No state found")
        return
    
    for account, email_ids in processor.processed_state.items():
        logger.info(f"  Account: {account}")
        logger.info(f"    Processed emails: {len(email_ids)}")
        if email_ids:
            logger.info(f"    Sample IDs: {email_ids[:3]}")

def add_test_emails(processor, account_name, count):
    """Add test emails to the state."""
    logger.info(f"Adding {count} test emails to state for account '{account_name}'")
    
    # Create test emails
    for i in range(count):
        # Create a test email
        email_data = {
            "subject": f"Test Email {i+1}",
            "from": "test@example.com",
            "to": "user@example.com",
            "date": datetime.now().isoformat(),
            "body": f"This is test email {i+1}"
        }
        
        # Mark it as processed
        processor._mark_email_as_processed(account_name, i+1000, email_data)
        
    logger.info(f"Added {count} test emails to state")

def clean_state(processor):
    """Clean up the state."""
    logger.info("Cleaning up state")
    processor._cleanup_processed_state()
    
    # Show the current state after cleanup
    view_state(processor)

def reset_state(processor, account_name=None):
    """Reset the state."""
    if account_name:
        logger.info(f"Resetting state for account '{account_name}'")
        if account_name in processor.processed_state:
            processor.processed_state[account_name] = []
            processor._save_processed_state()
            logger.info(f"Reset state for account '{account_name}'")
        else:
            logger.warning(f"Account '{account_name}' not found in state")
    else:
        logger.info("Resetting state for all accounts")
        processor.processed_state = {}
        processor._save_processed_state()
        logger.info("Reset state for all accounts")

def main():
    """Run the test script."""
    args = parse_args()
    
    # Create a processor to access the state
    processor = EmailProcessor(args.config)
    
    # Perform the requested action
    if args.action == "view":
        view_state(processor)
    
    elif args.action == "add":
        if not args.account:
            logger.error("Account name is required for 'add' action")
            return
        
        add_test_emails(processor, args.account, args.count)
        view_state(processor)
    
    elif args.action == "clean":
        clean_state(processor)
    
    elif args.action == "reset":
        reset_state(processor, args.account)
        view_state(processor)

if __name__ == "__main__":
    main() 