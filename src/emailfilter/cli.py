"""Command-line interface for the emailfilter package."""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

from emailfilter import categorizer, filter, imap_client

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
    
    return parser.parse_args()


def load_emails(file_path: str) -> List[Dict[str, str]]:
    """Load emails from a JSON file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading emails: {e}", file=sys.stderr)
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
            print(f"Invalid filter format: {f}. Use 'key:value'", file=sys.stderr)
    
    return filters


def handle_filter_command(args: argparse.Namespace) -> None:
    """Handle the filter command."""
    emails = load_emails(args.input)
    filters = parse_filters(args.filter)
    filtered_emails = filter.filter_emails(emails, filters)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(filtered_emails, f, indent=2)
    else:
        print(json.dumps(filtered_emails, indent=2))


def handle_categorize_command(args: argparse.Namespace) -> None:
    """Handle the categorize command."""
    emails = load_emails(args.input)
    
    try:
        if args.category == "all":
            # Categorize all emails and group by category
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
            all_categorized = categorizer.categorize_and_filter(emails)
            result = {
                args.category.capitalize(): all_categorized[category_map[args.category]]
            }
        
        # Output the results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result, indent=2))
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_imap_command(args: argparse.Namespace) -> None:
    """Handle the IMAP command."""
    try:
        # Create the email processor
        processor = imap_client.EmailProcessor(args.config)
        
        # Apply command-line overrides
        if args.dry_run:
            processor.options["move_emails"] = False
            processor.options["add_processed_flag"] = False
            processor.options["mark_as_read"] = False
        
        if args.max_emails:
            processor.options["max_emails_per_run"] = args.max_emails
        
        # Check if we should run in daemon mode
        if args.daemon:
            print("Starting continuous email monitoring...")
            print("Press Ctrl+C to stop")
            
            # Run in daemon mode
            if args.account:
                print(f"Note: In daemon mode, the --account option is ignored. All accounts will be monitored.")
            
            if args.folder:
                print(f"Note: In daemon mode, the --folder option is ignored. All configured folders will be monitored.")
            
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
                    
                    print(f"Processing account: {account}")
                    results = {account.name: processor.process_account(account)}
                    break
            
            if not account_found:
                print(f"Error: Account '{args.account}' not found in configuration", file=sys.stderr)
                sys.exit(1)
        else:
            # Process all accounts
            results = processor.process_all_accounts()
        
        # Print summary
        print("\nEmail Processing Summary:")
        print("=" * 50)
        
        for account_name, account_results in results.items():
            print(f"\nAccount: {account_name}")
            
            for folder, category_counts in account_results.items():
                print(f"  Folder: {folder}")
                
                total = sum(category_counts.values())
                if total == 0:
                    print("    No emails processed")
                    continue
                
                for category, count in category_counts.items():
                    if count > 0:
                        print(f"    {category}: {count} emails")
        
        print("\nProcessing complete!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_daemon_command(args: argparse.Namespace) -> None:
    """Handle the daemon command."""
    try:
        print("Starting Email Filter daemon service...")
        print("Press Ctrl+C to stop")
        
        # Create the email processor and start monitoring
        processor = imap_client.EmailProcessor(args.config)
        processor.start_monitoring()
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()
    
    # Check if version flag is set
    if args.version:
        print(f"Email Filter version {__version__}")
        sys.exit(0)
    
    # Default to filter command if none specified
    if not args.command:
        print("Error: No command specified. Use one of: filter, categorize, imap, daemon", file=sys.stderr)
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


if __name__ == "__main__":
    main() 