#!/usr/bin/env python3
"""Example script demonstrating how to use the IMAP email processing functionality."""

import os
import sys
from typing import Dict, List
from pprint import pprint

from emailfilter import imap_client

# Get the directory of this script
script_dir: str = os.path.dirname(os.path.abspath(__file__))
config_example: str = os.path.join(os.path.dirname(script_dir), "config.yaml.example")

# Check if a config file was provided
if len(sys.argv) != 2:
    print(f"Usage: python {sys.argv[0]} <config_file>")
    print(f"\nExample configuration file format can be found at: {config_example}")
    sys.exit(1)

config_path: str = sys.argv[1]

# Check if the config file exists
if not os.path.exists(config_path):
    print(f"Error: Config file not found: {config_path}")
    print(f"\nExample configuration file format can be found at: {config_example}")
    sys.exit(1)

print("Email Filter - IMAP Processing Example")
print("=" * 50)
print(f"Using configuration file: {config_path}")

# Create the email processor
processor: imap_client.EmailProcessor = imap_client.EmailProcessor(config_path)

# Print account information
print("\nConfigured Accounts:")
for i, account in enumerate(processor.accounts, 1):
    print(f"{i}. {account.name} ({account.email_address})")
    print(f"   Server: {account.imap_server}:{account.imap_port}")
    print(f"   Folders: {', '.join(account.folders)}")

# Print processing options
print("\nProcessing Options:")
for option, value in processor.options.items():
    print(f"- {option}: {value}")

# Ask for confirmation before proceeding
print("\nThis script will connect to your email accounts, categorize emails, and potentially move them.")
response: str = input("Do you want to proceed? (y/n): ")

if response.lower() != "y":
    print("Operation cancelled.")
    sys.exit(0)

# Process all accounts
print("\nProcessing accounts...")
results: Dict[str, Dict[str, Dict[imap_client.categorizer.EmailCategory, int]]] = processor.process_all_accounts()

# Print summary
print("\nEmail Processing Summary:")
print("=" * 50)

for account_name, account_results in results.items():
    print(f"\nAccount: {account_name}")
    
    for folder, category_counts in account_results.items():
        print(f"  Folder: {folder}")
        
        total: int = sum(category_counts.values())
        if total == 0:
            print("    No emails processed")
            continue
        
        for category, count in category_counts.items():
            if count > 0:
                print(f"    {category}: {count} emails")

print("\nProcessing complete!") 