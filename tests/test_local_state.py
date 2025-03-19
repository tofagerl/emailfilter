#!/usr/bin/env python
"""Test script to demonstrate the local state system for tracking processed emails."""

import os
import logging
import argparse
from datetime import datetime

from mailmind.sqlite_state_manager import SQLiteStateManager
from mailmind.models import Email

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test the local state system")
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
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Maximum age of state entries in days (for clean action)"
    )
    return parser.parse_args()

def view_state(state_manager):
    """View the current state."""
    logger.debug("Current state:")
    
    accounts = state_manager.get_accounts()
    if not accounts:
        logger.debug("  No accounts found in state")
        return
    
    total = 0
    for account in accounts:
        count = state_manager.get_processed_count(account)
        total += count
        logger.debug(f"  Account: {account}")
        logger.debug(f"    Processed emails: {count}")
    
    logger.debug(f"Total processed emails: {total}")

def add_test_emails(state_manager, account_name, count):
    """Add test emails to the state."""
    logger.debug(f"Adding {count} test emails to state for account '{account_name}'")
    
    # Create test emails
    for i in range(count):
        # Create a test email
        email = Email(
            subject=f"Test Email {i+1}",
            from_addr="test@example.com",
            to_addr="user@example.com",
            date=datetime.now().isoformat(),
            body=f"This is test email {i+1}",
            raw_message=b"",
            msg_id=i+1000,
            folder="INBOX"
        )
        
        # Mark it as processed
        state_manager.mark_email_as_processed(account_name, email)
        
    logger.debug(f"Added {count} test emails to state")

def clean_state(state_manager, max_age_days):
    """Clean up old state entries."""
    logger.debug(f"Cleaning up state entries older than {max_age_days} days")
    state_manager.cleanup_old_entries(max_age_days)
    
    # Show the current state after cleanup
    view_state(state_manager)

def reset_state(state_manager, account_name=None):
    """Reset the state for an account or all accounts."""
    if account_name:
        logger.debug(f"Resetting state for account '{account_name}'")
        deleted = state_manager.delete_account_entries(account_name)
        logger.debug(f"Reset state for account '{account_name}'. Deleted {deleted} entries.")
    else:
        logger.debug("Resetting state for all accounts")
        # Delete the database file
        if os.path.exists(state_manager.db_file_path):
            os.remove(state_manager.db_file_path)
            logger.debug("State database deleted")
        
        # Reinitialize the database
        state_manager._init_db()
        logger.debug("State database reinitialized")
    
    return state_manager

def main():
    """Run the test script."""
    args = parse_args()
    
    # Create a state manager with default path
    state_manager = SQLiteStateManager()
    
    # Perform the requested action
    if args.action == "view":
        view_state(state_manager)
    
    elif args.action == "add":
        if not args.account:
            logger.error("Account name is required for 'add' action")
            return
        
        add_test_emails(state_manager, args.account, args.count)
        view_state(state_manager)
    
    elif args.action == "clean":
        clean_state(state_manager, args.max_age_days)
    
    elif args.action == "reset":
        state_manager = reset_state(state_manager, args.account)
        view_state(state_manager)

if __name__ == "__main__":
    main() 