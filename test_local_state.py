#!/usr/bin/env python3
"""Test script for the local state system."""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Optional

from mailmind.sqlite_state_manager import SQLiteStateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test the local state system")
    parser.add_argument(
        "action",
        choices=["view", "add", "clean", "reset"],
        help="Action to perform"
    )
    parser.add_argument(
        "--account",
        type=str,
        help="Account name for add/reset actions"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of test emails to add (default: 5)"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Maximum age of state entries in days (for clean action)"
    )
    return parser.parse_args()


def view_state(state_manager: SQLiteStateManager) -> None:
    """View the current state."""
    logger.info("Current state:")
    entries = state_manager.get_all_entries()
    
    if not entries:
        logger.info("No entries found")
        return
    
    for entry in entries:
        logger.info(f"Entry: {entry}")


def add_test_emails(state_manager: SQLiteStateManager, account: str, count: int) -> None:
    """Add test emails to the state."""
    logger.info(f"Adding {count} test emails for account: {account}")
    
    for i in range(count):
        email_id = f"test_email_{i}"
        state_manager.add_entry(
            account=account,
            message_id=email_id,
            sender=f"test{i}@example.com",
            subject=f"Test Email {i}",
            date=datetime.now() - timedelta(days=i)
        )
    
    logger.info("Test emails added successfully")


def clean_state(state_manager: SQLiteStateManager, max_age_days: int) -> None:
    """Clean up old state entries."""
    logger.info(f"Cleaning state entries older than {max_age_days} days")
    state_manager.clean_old_entries(max_age_days)
    logger.info("State cleaned successfully")


def reset_state(state_manager: SQLiteStateManager, account: Optional[str] = None) -> SQLiteStateManager:
    """Reset the state for all accounts or a specific account."""
    if account:
        logger.info(f"Resetting state for account: {account}")
        state_manager.reset_account(account)
    else:
        logger.info("Resetting state for all accounts")
        state_manager.reset_all()
    
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