"""Command-line interface for the emailfilter package."""

import argparse
import json
import os
import sys
import logging
from typing import Dict, List, Optional

from emailfilter import categorizer, filter, imap_client

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Get version from package
try:
    from importlib.metadata import version
    __version__ = version("emailfilter")
except (ImportError, ModuleNotFoundError):
    __version__ = "0.1.0"  # Default version if not installed


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Filter and categorize emails")
    
    # Add version argument
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    
    # Add logging level argument
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Filter command
    filter_parser = subparsers.add_parser("filter", help="Filter emails based on criteria")
    filter_parser.add_argument(
        "--input", "-i", 
        type=str, 
        required=True,
        help="Path to JSON file containing emails"
    )
    filter_parser.add_argument(
        "--output", "-o", 
        type=str, 
        help="Path to output filtered emails (default: stdout)"
    )
    filter_parser.add_argument(
        "--filter", "-f", 
        type=str, 
        action="append",
        help="Filter criteria in format 'key:value' (can be used multiple times)"
    )
    
    # Categorize command
    categorize_parser = subparsers.add_parser("categorize", help="Categorize emails using OpenAI API")
    categorize_parser.add_argument(
        "--input", "-i", 
        type=str, 
        required=True,
        help="Path to JSON file containing emails"
    )
    categorize_parser.add_argument(
        "--output", "-o", 
        type=str, 
        help="Path to output categorized emails (default: stdout)"
    )
    categorize_parser.add_argument(
        "--category", "-c",
        type=str,
        choices=["spam", "receipts", "promotions", "updates", "inbox", "all"],
        default="all",
        help="Category to filter by (default: all)"
    )
    categorize_parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of emails to process in each batch (default: 10)"
    )
    categorize_parser.add_argument(
        "--custom-categories",
        action="store_true",
        help="Use custom categories defined in a JSON file"
    )
    categorize_parser.add_argument(
        "--categories-file",
        type=str,
        help="Path to JSON file containing custom categories"
    )
    categorize_parser.add_argument(
        "--cleanup-logs",
        action="store_true",
        help="Clean up old log entries (older than 7 days)"
    )
    
    # IMAP command
    imap_parser = subparsers.add_parser("imap", help="Process emails from IMAP accounts")
    imap_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )
    imap_parser.add_argument(
        "--account", "-a",
        type=str,
        help="Process only the specified account (by name)"
    )
    imap_parser.add_argument(
        "--folder", "-f",
        type=str,
        help="Process only the specified folder"
    )
    imap_parser.add_argument(
        "--max-emails", "-m",
        type=int,
        default=100,
        help="Maximum number of emails to process per folder (default: 100)"
    )
    imap_parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Categorize emails but don't move them or mark them as processed"
    )
    imap_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in continuous monitoring mode using IMAP IDLE"
    )
    
    # Daemon command (dedicated command for running as a service)
    daemon_parser = subparsers.add_parser("daemon", help="Run as a daemon service with continuous email monitoring")
    daemon_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Manage OpenAI interaction logs")
    logs_subparsers = logs_parser.add_subparsers(dest="logs_command", help="Logs command")
    
    # View logs command
    view_logs_parser = logs_subparsers.add_parser("view", help="View OpenAI interaction logs")
    view_logs_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of log entries to display (default: 10)"
    )
    view_logs_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Path to output logs (default: stdout)"
    )
    
    # Clean logs command
    clean_logs_parser = logs_subparsers.add_parser("clean", help="Clean up old log entries")
    clean_logs_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Delete log entries older than this many days (default: 7)"
    )
    
    return parser.parse_args()


def load_emails(file_path: str) -> List[Dict[str, str]]:
    """Load emails from a JSON file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading emails: {e}")
        sys.exit(1)


def load_custom_categories(file_path: str) -> List[Dict[str, str]]:
    """Load custom categories from a JSON file."""
    try:
        with open(file_path, "r") as f:
            categories = json.load(f)
            logger.info(f"Loaded {len(categories)} custom categories from {file_path}")
            return categories
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading custom categories: {e}")
        sys.exit(1)


def parse_filters(filter_args: Optional[List[str]]) -> Optional[Dict[str, str]]:
    """Parse filter arguments into a dictionary."""
    if not filter_args:
        return None
    
    filters = {}
    for f in filter_args:
        try:
            key, value = f.split(":", 1)
            filters[key] = value
        except ValueError:
            logger.error(f"Invalid filter format: {f}. Use 'key:value'")
    
    return filters


def handle_filter_command(args: argparse.Namespace) -> None:
    """Handle the filter command."""
    logger.info(f"Loading emails from {args.input}")
    emails = load_emails(args.input)
    
    filters = parse_filters(args.filter)
    logger.info(f"Applying filters: {filters}")
    filtered_emails = filter.filter_emails(emails, filters)
    
    logger.info(f"Filtered {len(filtered_emails)} emails out of {len(emails)}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(filtered_emails, f, indent=2)
        logger.info(f"Wrote filtered emails to {args.output}")
    else:
        print(json.dumps(filtered_emails, indent=2))


def handle_categorize_command(args: argparse.Namespace) -> None:
    """Handle the categorize command."""
    logger.info(f"Loading emails from {args.input}")
    emails = load_emails(args.input)
    
    # Get OpenAI API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Set the API key
    categorizer.set_api_key(api_key)
    
    # Clean up old logs if requested
    if args.cleanup_logs:
        deleted_count = categorizer.cleanup_old_logs()
        logger.info(f"Cleaned up {deleted_count} old log entries")
    
    try:
        if args.custom_categories:
            # Use custom categories if specified
            if args.categories_file:
                categories = load_custom_categories(args.categories_file)
            else:
                # Default custom categories
                categories = [
                    {"id": 1, "name": "SPAM", "description": "Unwanted, unsolicited emails that might be scams or junk"},
                    {"id": 2, "name": "RECEIPTS", "description": "Transaction confirmations, receipts, order updates"},
                    {"id": 3, "name": "PROMOTIONS", "description": "Marketing emails, newsletters, offers, discounts"},
                    {"id": 4, "name": "UPDATES", "description": "Non-urgent notifications, social media updates, news"},
                    {"id": 5, "name": "INBOX", "description": "Important emails that need attention or quick response"}
                ]
                logger.info(f"Using default custom categories")
            
            if args.category == "all":
                # Categorize all emails with custom categories
                logger.info(f"Categorizing {len(emails)} emails with custom categories")
                categorized = categorizer.batch_categorize_emails_with_custom_categories(emails, categories)
                
                # Group emails by category
                result = {}
                for item in categorized:
                    category_name = item["category"]["name"]
                    if category_name not in result:
                        result[category_name] = []
                    result[category_name].append(item["email"])
            else:
                # Filter by the specified category
                logger.info(f"Categorizing and filtering emails by category: {args.category}")
                all_categorized = categorizer.categorize_and_filter_with_custom_categories(emails, categories)
                result = {
                    args.category.capitalize(): all_categorized.get(args.category.upper(), [])
                }
        else:
            # Use default categories
            if args.category == "all":
                # Categorize all emails and group by category
                logger.info(f"Categorizing {len(emails)} emails with default categories")
                categorized = categorizer.batch_categorize_emails(emails, args.batch_size)
                
                # Group emails by category
                result = {}
                for item in categorized:
                    category = item["category"]
                    if category not in result:
                        result[category] = []
                    result[category].append(item["email"])
            else:
                # Map string category to enum
                category_map = {
                    "spam": categorizer.EmailCategory.SPAM,
                    "receipts": categorizer.EmailCategory.RECEIPTS,
                    "promotions": categorizer.EmailCategory.PROMOTIONS,
                    "updates": categorizer.EmailCategory.UPDATES,
                    "inbox": categorizer.EmailCategory.INBOX
                }
                
                # Categorize all emails and filter by the specified category
                logger.info(f"Categorizing and filtering emails by category: {args.category}")
                all_categorized = categorizer.categorize_and_filter(emails)
                result = {
                    args.category.capitalize(): all_categorized[category_map[args.category]]
                }
        
        # Output the results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Wrote categorized emails to {args.output}")
        else:
            print(json.dumps(result, indent=2))
            
    except ValueError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def handle_imap_command(args: argparse.Namespace) -> None:
    """Handle the IMAP command."""
    try:
        # Create the email processor
        logger.info(f"Loading configuration from {args.config}")
        processor = imap_client.EmailProcessor(args.config)
        
        # Apply command-line overrides
        if args.dry_run:
            processor.options["move_emails"] = False
            processor.options["add_processed_flag"] = False
            processor.options["mark_as_read"] = False
            logger.info("Running in dry-run mode (no changes will be made)")
        
        if args.max_emails:
            processor.options["max_emails_per_run"] = args.max_emails
            logger.info(f"Set maximum emails per run to {args.max_emails}")
        
        # Check if we should run in daemon mode
        if args.daemon:
            logger.info("Starting continuous email monitoring...")
            logger.info("Press Ctrl+C to stop")
            
            # Run in daemon mode
            if args.account:
                logger.info("Note: In daemon mode, the --account option is ignored. All accounts will be monitored.")
            
            if args.folder:
                logger.info("Note: In daemon mode, the --folder option is ignored. All configured folders will be monitored.")
            
            processor.start_monitoring()
            return
        
        # Process accounts
        if args.account:
            # Process only the specified account
            account_found = False
            for account in processor.accounts:
                if account.name == args.account:
                    account_found = True
                    
                    # Override folders if specified
                    if args.folder:
                        account.folders = [args.folder]
                        logger.info(f"Processing only folder: {args.folder}")
                    
                    logger.info(f"Processing account: {account}")
                    results = {account.name: processor.process_account(account)}
                    break
            
            if not account_found:
                logger.error(f"Account '{args.account}' not found in configuration")
                sys.exit(1)
        else:
            # Process all accounts
            logger.info("Processing all accounts")
            results = processor.process_all_accounts()
        
        # Print summary
        logger.info("\nEmail Processing Summary:")
        logger.info("=" * 50)
        
        for account_name, account_results in results.items():
            logger.info(f"\nAccount: {account_name}")
            
            for folder, category_counts in account_results.items():
                logger.info(f"  Folder: {folder}")
                
                total = sum(category_counts.values())
                if total == 0:
                    logger.info("    No emails processed")
                    continue
                
                for category, count in category_counts.items():
                    if count > 0:
                        logger.info(f"    {category}: {count} emails")
        
        logger.info("\nProcessing complete!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def handle_daemon_command(args: argparse.Namespace) -> None:
    """Handle the daemon command."""
    try:
        logger.info("Starting Email Filter daemon service...")
        logger.info("Press Ctrl+C to stop")
        
        # Create the email processor and start monitoring
        processor = imap_client.EmailProcessor(args.config)
        processor.start_monitoring()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def handle_logs_command(args: argparse.Namespace) -> None:
    """Handle the logs command."""
    if args.logs_command == "view":
        try:
            log_file = 'logs/detailed_openai_logs.jsonl'
            if not os.path.exists(log_file):
                logger.error(f"Log file not found: {log_file}")
                sys.exit(1)
            
            # Read the log file
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Parse the log entries
            log_entries = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    log_entries.append(entry)
                except json.JSONDecodeError:
                    continue
            
            # Sort by timestamp (newest first)
            log_entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Limit the number of entries
            log_entries = log_entries[:args.limit]
            
            # Format the output
            output = []
            for entry in log_entries:
                output.append({
                    'timestamp': entry.get('timestamp', ''),
                    'email_subject': entry.get('email_subject', ''),
                    'email_from': entry.get('email_from', ''),
                    'category_result': entry.get('category_result', ''),
                    'response_received': entry.get('response_received', '')
                })
            
            # Output the results
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(output, f, indent=2)
                logger.info(f"Wrote log entries to {args.output}")
            else:
                print(json.dumps(output, indent=2))
            
        except Exception as e:
            logger.error(f"Error viewing logs: {e}")
            sys.exit(1)
    
    elif args.logs_command == "clean":
        try:
            deleted_count = categorizer.cleanup_old_logs(args.days)
            logger.info(f"Cleaned up {deleted_count} log entries older than {args.days} days")
        except Exception as e:
            logger.error(f"Error cleaning logs: {e}")
            sys.exit(1)
    
    else:
        logger.error(f"Unknown logs command: {args.logs_command}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    logger.setLevel(getattr(logging, args.log_level))
    categorizer.logger.setLevel(getattr(logging, args.log_level))
    
    # Check if version flag is set
    if args.version:
        print(f"Email Filter version {__version__}")
        sys.exit(0)
    
    # Default to filter command if none specified
    if not args.command:
        logger.error("No command specified. Use one of: filter, categorize, imap, daemon, logs")
        sys.exit(1)
    
    # Handle the appropriate command
    if args.command == "filter":
        handle_filter_command(args)
    elif args.command == "categorize":
        handle_categorize_command(args)
    elif args.command == "imap":
        handle_imap_command(args)
    elif args.command == "daemon":
        handle_daemon_command(args)
    elif args.command == "logs":
        handle_logs_command(args)


if __name__ == "__main__":
    main() 