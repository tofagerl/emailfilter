#!/usr/bin/env python3
"""Example script demonstrating how to run the email filter in daemon mode."""

import os
import sys
import time

# Use the new email_processor module instead of the deprecated imap_client
from emailfilter.email_processor import EmailProcessor

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
config_example = os.path.join(os.path.dirname(script_dir), "config.yaml.example")

# Check if a config file was provided
if len(sys.argv) != 2:
    print(f"Usage: python {sys.argv[0]} <config_file>")
    print(f"\nExample configuration file format can be found at: {config_example}")
    sys.exit(1)

config_path = sys.argv[1]

# Check if the config file exists
if not os.path.exists(config_path):
    print(f"Error: Config file not found: {config_path}")
    print(f"\nExample configuration file format can be found at: {config_example}")
    sys.exit(1)

print("Email Filter - Daemon Mode Example")
print("=" * 50)
print(f"Using configuration file: {config_path}")

# Create the email processor
processor = EmailProcessor(config_path)

# Print account information
print("\nConfigured Accounts:")
for i, account in enumerate(processor.config_manager.accounts, 1):
    print(f"{i}. {account.name} ({account.email})")
    print(f"   Server: {account.imap_server}:{account.imap_port}")
    print(f"   Folders: {', '.join(account.folders)}")

# Print daemon options
print("\nDaemon Options:")
print(f"- IDLE Timeout: {processor.config_manager.options.idle_timeout} seconds")
print(f"- Max Emails Per Run: {processor.config_manager.options.max_emails_per_run}")

# Print processing options
print("\nProcessing Options:")
for option, value in vars(processor.config_manager.options).items():
    if option not in ["idle_timeout", "max_emails_per_run"]:
        print(f"- {option}: {value}")

# Ask for confirmation before proceeding
print("\nThis script will start a daemon that continuously monitors your email accounts.")
print("It will process new emails as they arrive and categorize them using OpenAI's API.")
print("The daemon will run until you press Ctrl+C to stop it.")
response = input("Do you want to proceed? (y/n): ")

if response.lower() != "y":
    print("Operation cancelled.")
    sys.exit(0)

# Start monitoring
print("\nStarting email monitoring daemon...")
print("Press Ctrl+C to stop")

try:
    # Start the monitoring process
    processor.start_monitoring()
except KeyboardInterrupt:
    print("\nDaemon stopped by user.") 