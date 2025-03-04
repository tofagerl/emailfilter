"""Command-line interface for emailfilter."""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

from emailfilter import categorizer
from emailfilter.email_processor import main as email_processor_main
from emailfilter.models import Email
from emailfilter.sqlite_state_manager import SQLiteStateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def handle_categorize_command(args):
    """Handle the categorize command."""
    try:
        # Load emails from input file
        with open(args.input, "r") as f:
            emails = json.load(f)
        
        # Load API key from config
        try:
            categorizer.load_api_key(args.config)
        except Exception as e:
            logger.error(f"Error loading API key: {e}")
            sys.exit(1)
        
        # Clean up old logs if requested
        if args.cleanup_logs:
            deleted = categorizer.cleanup_old_logs(args.cleanup_logs_days)
            logger.info(f"Deleted {deleted} old log files")
        
        # Categorize emails
        if args.custom_categories:
            with open(args.custom_categories, "r") as f:
                categories = json.load(f)
            
            if args.category != "all":
                logger.info(f"Filtering by custom category: {args.category}")
                results = categorizer.categorize_and_filter_with_custom_categories(emails, categories)
                filtered_emails = results.get(args.category, [])
                logger.info(f"Found {len(filtered_emails)} emails in category {args.category}")
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(filtered_emails, f, indent=2)
            else:
                logger.info("Categorizing emails with custom categories")
                results = categorizer.categorize_and_filter_with_custom_categories(emails, categories)
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(results, f, indent=2)
                
                # Print summary
                for category, emails in results.items():
                    logger.info(f"Category {category}: {len(emails)} emails")
        else:
            if args.category != "all":
                logger.info(f"Filtering by category: {args.category}")
                category_enum = getattr(categorizer.EmailCategory, args.category.upper())
                results = categorizer.categorize_and_filter(emails)
                filtered_emails = results.get(category_enum, [])
                logger.info(f"Found {len(filtered_emails)} emails in category {category_enum}")
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(filtered_emails, f, indent=2)
            else:
                logger.info("Categorizing emails")
                results = categorizer.categorize_and_filter(emails)
                
                # Convert results to serializable format
                serializable_results = {}
                for category, emails in results.items():
                    serializable_results[category.name.lower()] = emails
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(serializable_results, f, indent=2)
                
                # Print summary
                for category, emails in results.items():
                    logger.info(f"Category {category}: {len(emails)} emails")
    except Exception as e:
        logger.error(f"Error categorizing email: {e}")
        sys.exit(1)


def handle_imap_command(args):
    """Handle the imap command."""
    try:
        # Run the email processor
        email_processor_main(args.config, args.daemon)
    except Exception as e:
        logger.error(f"Error processing emails: {e}")
        sys.exit(1)


def handle_filter_command(args):
    """Handle the filter command."""
    try:
        # Load emails from input file
        with open(args.input, "r") as f:
            emails = json.load(f)
        
        # Load filters from filter file
        with open(args.filters, "r") as f:
            filters = json.load(f)
        
        # Apply filters
        from emailfilter.filter import filter_emails
        filtered_emails = filter_emails(emails, filters)
        
        # Write results to output file
        with open(args.output, "w") as f:
            json.dump(filtered_emails, f, indent=2)
        
        # Print summary
        for filter_name, emails in filtered_emails.items():
            logger.info(f"Filter {filter_name}: {len(emails)} emails")
    except Exception as e:
        logger.error(f"Error filtering emails: {e}")
        sys.exit(1)


def handle_state_command(args):
    """Handle the state command."""
    try:
        # Initialize state manager
        state_dir = os.path.expanduser("~/.emailfilter")
        os.makedirs(state_dir, exist_ok=True)
        state_manager = SQLiteStateManager(os.path.join(state_dir, "processed_emails.db"))
        
        if args.action == "view":
            # View state
            if args.account:
                count = state_manager.get_processed_count(args.account)
                logger.info(f"Account '{args.account}' has {count} processed emails")
            else:
                accounts = state_manager.get_accounts()
                logger.info(f"Found {len(accounts)} accounts in the state database")
                for account in accounts:
                    count = state_manager.get_processed_count(account)
                    logger.info(f"Account '{account}' has {count} processed emails")
                
                total = state_manager.get_processed_count()
                logger.info(f"Total processed emails: {total}")
        
        elif args.action == "clean":
            # Clean state
            state_manager.cleanup_old_entries(args.max_age_days)
            logger.info(f"Cleaned up state entries older than {args.max_age_days} days")
        
        elif args.action == "reset":
            # Reset state by recreating the database
            if args.account:
                logger.warning(f"This will reset the state for account '{args.account}'. All emails will be reprocessed.")
                if args.force or input("Are you sure? (y/n): ").lower() == "y":
                    # Delete all entries for this account
                    deleted = state_manager.delete_account_entries(args.account)
                    logger.info(f"Reset state for account '{args.account}'. Deleted {deleted} entries.")
            else:
                logger.warning("This will reset the state for all accounts. All emails will be reprocessed.")
                if args.force or input("Are you sure? (y/n): ").lower() == "y":
                    # Delete the database file and recreate it
                    db_path = os.path.join(state_dir, "processed_emails.db")
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        logger.info("State database deleted")
                    
                    # Reinitialize the database
                    state_manager = SQLiteStateManager(db_path)
                    logger.info("State database reinitialized")
    
    except Exception as e:
        logger.error(f"Error managing state: {e}")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Email filtering and categorization tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Categorize command
    categorize_parser = subparsers.add_parser("categorize", help="Categorize emails")
    categorize_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )
    categorize_parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Path to input JSON file containing emails"
    )
    categorize_parser.add_argument(
        "--output", "-o",
        type=str,
        default="categorized_emails.json",
        help="Path to output JSON file (default: categorized_emails.json)"
    )
    categorize_parser.add_argument(
        "--category", "-cat",
        type=str,
        choices=["spam", "receipts", "promotions", "updates", "inbox", "all"],
        default="all",
        help="Category to filter by (default: all)"
    )
    categorize_parser.add_argument(
        "--custom-categories",
        type=str,
        help="Path to JSON file containing custom categories"
    )
    categorize_parser.add_argument(
        "--cleanup-logs",
        action="store_true",
        help="Clean up old log files"
    )
    categorize_parser.add_argument(
        "--cleanup-logs-days",
        type=int,
        default=7,
        help="Maximum age of log files in days (default: 7)"
    )
    categorize_parser.set_defaults(func=handle_categorize_command)
    
    # IMAP command
    imap_parser = subparsers.add_parser("imap", help="Process emails from IMAP accounts")
    imap_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )
    imap_parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run in daemon mode (continuous monitoring)"
    )
    imap_parser.set_defaults(func=handle_imap_command)
    
    # Filter command
    filter_parser = subparsers.add_parser("filter", help="Filter emails")
    filter_parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Path to input JSON file containing emails"
    )
    filter_parser.add_argument(
        "--output", "-o",
        type=str,
        default="filtered_emails.json",
        help="Path to output JSON file (default: filtered_emails.json)"
    )
    filter_parser.add_argument(
        "--filters", "-f",
        type=str,
        required=True,
        help="Path to JSON file containing filters"
    )
    filter_parser.set_defaults(func=handle_filter_command)
    
    # State command
    state_parser = subparsers.add_parser("state", help="Manage the local state")
    state_parser.add_argument(
        "action",
        choices=["view", "clean", "reset"],
        help="Action to perform on the state"
    )
    state_parser.add_argument(
        "--account", "-a",
        type=str,
        help="Account to manage state for"
    )
    state_parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Maximum age of state entries in days (for clean action)"
    )
    state_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reset without confirmation"
    )
    state_parser.set_defaults(func=handle_state_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run command
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 