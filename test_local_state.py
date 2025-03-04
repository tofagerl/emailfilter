#!/usr/bin/env python
"""Test script to demonstrate the local state system for tracking processed emails."""

import os
import logging
import argparse
from datetime import datetime

from emailfilter.sqlite_state_manager import SQLiteStateManager
from emailfilter.models import Email

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
    logger.info("Current state:")
    
    accounts = state_manager.get_accounts()
    if not accounts:
        logger.info("  No accounts found in state")
        return
    
    for account in accounts:
        count = state_manager.get_processed_count(account)
        logger.info(f"  Account: {account}")
        logger.info(f"    Processed emails: {count}")
    
    total = state_manager.get_processed_count()
    logger.info(f"Total processed emails: {total}")

def add_test_emails(state_manager, account_name, count):
    """Add test emails to the state."""
    logger.info(f"Adding {count} test emails to state for account '{account_name}'")
    
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
        
    logger.info(f"Added {count} test emails to state")

def clean_state(state_manager, max_age_days):
    """Clean up the state."""
    logger.info(f"Cleaning up state entries older than {max_age_days} days")
    state_manager.cleanup_old_entries(max_age_days)
    
    # Show the current state after cleanup
    view_state(state_manager)

def reset_state(state_manager, account_name=None):
    """Reset the state."""
    if account_name:
        logger.info(f"Resetting state for account '{account_name}'")
        deleted = state_manager.delete_account_entries(account_name)
        logger.info(f"Reset state for account '{account_name}'. Deleted {deleted} entries.")
    else:
        logger.info("Resetting state for all accounts")
        # Delete the database file and recreate it
        db_path = state_manager.db_file_path
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info("State database deleted")
        
        # Reinitialize the database
        state_manager = SQLiteStateManager(db_path)
        logger.info("State database reinitialized")
    
    return state_manager

def main():
    """Run the test script."""
    args = parse_args()
    
    # Create a state manager
    state_dir = os.path.expanduser("~/.emailfilter")
    os.makedirs(state_dir, exist_ok=True)
    state_manager = SQLiteStateManager(os.path.join(state_dir, "processed_emails.db"))
    
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