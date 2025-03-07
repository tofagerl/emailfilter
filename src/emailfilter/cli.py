"""Command-line interface for emailfilter."""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

from emailfilter import categorizer
from emailfilter.email_processor import main as email_processor_main
from emailfilter.models import Email, EmailAccount, Category
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
        
        # Create a mock account with the appropriate categories
        mock_account = EmailAccount(
            name="CLI",
            email_address="cli@example.com",
            password="",
            imap_server="",
            categories=[
                Category("SPAM", "Unwanted or malicious emails", "[Spam]"),
                Category("RECEIPTS", "Purchase confirmations and receipts", "[Receipts]"),
                Category("PROMOTIONS", "Marketing and promotional emails", "[Promotions]"),
                Category("UPDATES", "Updates and notifications", "[Updates]"),
                Category("INBOX", "Important emails that need attention", "INBOX")
            ]
        )
        
        # Categorize emails
        if args.custom_categories:
            # Load custom categories from file
            with open(args.custom_categories, "r") as f:
                custom_categories_data = json.load(f)
            
            # Create Category objects
            categories = []
            for cat in custom_categories_data:
                categories.append(Category(
                    name=cat.get("name", "").upper(),
                    description=cat.get("description", ""),
                    foldername=cat.get("foldername", "INBOX")
                ))
            
            # Create mock account
            mock_account = EmailAccount(
                name="CLI",
                email_address="cli@example.com",
                password="",
                imap_server="",
                categories=categories
            )
            
            # Categorize emails
            if args.category != "all":
                logger.info(f"Filtering by category: {args.category}")
                
                # Categorize all emails
                results = []
                for i in range(0, len(emails), args.batch_size):
                    batch = emails[i:i+args.batch_size]
                    batch_results = categorizer.batch_categorize_emails_for_account(
                        batch, mock_account, args.batch_size, args.model
                    )
                    results.extend(batch_results)
                
                # Filter by category
                filtered_emails = []
                for i, email in enumerate(emails):
                    if i < len(results) and results[i]["category"].upper() == args.category.upper():
                        filtered_emails.append(email)
                
                logger.info(f"Found {len(filtered_emails)} emails in category {args.category}")
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(filtered_emails, f, indent=2)
            else:
                logger.info("Categorizing emails")
                
                # Categorize all emails
                all_results = {}
                for cat in categories:
                    all_results[cat.name.lower()] = []
                
                for i in range(0, len(emails), args.batch_size):
                    batch = emails[i:i+args.batch_size]
                    batch_results = categorizer.batch_categorize_emails_for_account(
                        batch, mock_account, args.batch_size, args.model
                    )
                    
                    # Group by category
                    for j, email in enumerate(batch):
                        if j < len(batch_results):
                            category = batch_results[j]["category"].lower()
                            all_results[category].append(email)
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(all_results, f, indent=2)
                
                # Print summary
                for category, emails in all_results.items():
                    logger.info(f"Category {category}: {len(emails)} emails")
        else:
            # Use default categories
            default_categories = [
                Category("SPAM", "Unwanted or malicious emails", "[Spam]"),
                Category("RECEIPTS", "Purchase confirmations and receipts", "[Receipts]"),
                Category("PROMOTIONS", "Marketing and promotional emails", "[Promotions]"),
                Category("UPDATES", "Updates and notifications", "[Updates]"),
                Category("INBOX", "Important emails that need attention", "INBOX")
            ]
            
            # Create mock account
            mock_account = EmailAccount(
                name="CLI",
                email_address="cli@example.com",
                password="",
                imap_server="",
                categories=default_categories
            )
            
            # Categorize emails
            if args.category != "all":
                logger.info(f"Filtering by category: {args.category}")
                
                # Categorize all emails
                results = []
                for i in range(0, len(emails), args.batch_size):
                    batch = emails[i:i+args.batch_size]
                    batch_results = categorizer.batch_categorize_emails_for_account(
                        batch, mock_account, args.batch_size, args.model
                    )
                    results.extend(batch_results)
                
                # Filter by category
                filtered_emails = []
                for i, email in enumerate(emails):
                    if i < len(results) and results[i]["category"].upper() == args.category.upper():
                        filtered_emails.append(email)
                
                logger.info(f"Found {len(filtered_emails)} emails in category {args.category}")
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(filtered_emails, f, indent=2)
            else:
                logger.info("Categorizing emails")
                
                # Categorize all emails
                all_results = {cat.name.lower(): [] for cat in default_categories}
                
                for i in range(0, len(emails), args.batch_size):
                    batch = emails[i:i+args.batch_size]
                    batch_results = categorizer.batch_categorize_emails_for_account(
                        batch, mock_account, args.batch_size, args.model
                    )
                    
                    # Group by category
                    for j, email in enumerate(batch):
                        if j < len(batch_results):
                            category = batch_results[j]["category"].lower()
                            all_results[category].append(email)
                
                # Write results to output file
                with open(args.output, "w") as f:
                    json.dump(all_results, f, indent=2)
                
                # Print summary
                for category, emails in all_results.items():
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
        # Initialize state manager with default path
        state_manager = SQLiteStateManager()
        
        if args.action == "view":
            # View state
            if args.account:
                count = state_manager.get_processed_count(args.account)
                logger.info(f"Account '{args.account}' has {count} processed emails")
                
                # Show category stats if requested
                if args.stats:
                    stats = state_manager.get_category_stats(args.account)
                    logger.info(f"Category statistics for account '{args.account}':")
                    for category, count in stats.items():
                        logger.info(f"  {category}: {count} emails")
            else:
                accounts = state_manager.get_accounts()
                logger.info(f"Found {len(accounts)} accounts in the state database")
                for account in accounts:
                    count = state_manager.get_processed_count(account)
                    logger.info(f"Account '{account}' has {count} processed emails")
                    
                    # Show category stats if requested
                    if args.stats:
                        stats = state_manager.get_category_stats(account)
                        logger.info(f"  Category statistics:")
                        for category, count in stats.items():
                            logger.info(f"    {category}: {count} emails")
                
                total = state_manager.get_processed_count()
                logger.info(f"Total processed emails: {total}")
        
        elif args.action == "search":
            # Search for emails
            results = state_manager.query_processed_emails(
                account_name=args.account,
                from_addr=args.from_addr,
                to_addr=args.to_addr,
                subject=args.subject,
                category=args.category,
                limit=args.limit,
                offset=args.offset
            )
            
            if results:
                logger.info(f"Found {len(results)} matching emails:")
                for i, email in enumerate(results):
                    logger.info(f"Email {i+1}:")
                    logger.info(f"  Account: {email['account_name']}")
                    logger.info(f"  From: {email['from_addr']}")
                    logger.info(f"  To: {email['to_addr']}")
                    logger.info(f"  Subject: {email['subject']}")
                    logger.info(f"  Category: {email['category']}")
                    logger.info(f"  Processed: {email['processed_date']}")
                    logger.info("")
                
                if len(results) == args.limit:
                    logger.info(f"Showing {args.limit} results. Use --offset to see more.")
            else:
                logger.info("No matching emails found.")
        
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
                    # Get the database path
                    db_path = state_manager.db_file_path
                    
                    # Delete the database file and recreate it
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
    categorize_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for categorization"
    )
    categorize_parser.add_argument(
        "--model",
        type=str,
        help="Model to use for categorization"
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
        choices=["view", "search", "clean", "reset"],
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
    state_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show category statistics"
    )
    state_parser.add_argument(
        "--from-addr",
        type=str,
        help="From address for search"
    )
    state_parser.add_argument(
        "--to-addr",
        type=str,
        help="To address for search"
    )
    state_parser.add_argument(
        "--subject",
        type=str,
        help="Subject for search"
    )
    state_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of results to show (default: 10)"
    )
    state_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset for paginated results"
    )
    state_parser.add_argument(
        "--category",
        type=str,
        choices=["spam", "receipts", "promotions", "updates", "inbox", "all"],
        help="Category for search"
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