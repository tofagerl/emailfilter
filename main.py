#!/usr/bin/env python3
"""
Email Filter - A Python application for filtering and processing emails.

This is a simple entry point that demonstrates the OpenAI GPT-4o-mini based email categorization.
"""

import json
import os
import sys
from typing import Dict, List, Any

from emailfilter import categorizer
from emailfilter.models import EmailAccount, Category


def main() -> None:
    """Main entry point for the application."""
    print("Email Filter - OpenAI GPT-4o-mini powered Email Categorization")
    print("=" * 50)
    
    # Check if OpenAI API key is set
    try:
        categorizer.initialize_openai_client(config_path="config.yaml")
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease add your OpenAI API key to your config.yaml file:")
        print("openai_api_key: your_api_key_here")
        print("\nUsage: python main.py <email_json_file>")
        print("\nExample: python main.py examples/sample_emails.json")
        sys.exit(1)
    
    # Check if a file was provided
    if len(sys.argv) < 2:
        print("Usage: python main.py <email_json_file>")
        print("\nExample: python main.py examples/sample_emails.json")
        sys.exit(1)
    
    # Load emails from the provided file
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    try:
        with open(file_path, "r") as f:
            emails = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON file: {file_path}")
        sys.exit(1)
    
    if not isinstance(emails, list):
        print(f"Error: Expected a list of emails in {file_path}")
        sys.exit(1)
    
    # Create an account with default categories
    account = EmailAccount(
        name="Default",
        email_address="default@example.com",
        password="",
        imap_server="",
        categories=[
            Category("SPAM", "Unwanted emails", "[Spam]"),
            Category("RECEIPTS", "Order confirmations", "[Receipts]"),
            Category("PROMOTIONS", "Marketing emails", "[Promotions]"),
            Category("UPDATES", "Notifications", "[Updates]"),
            Category("INBOX", "Important emails", "INBOX")
        ]
    )
    
    # Categorize emails
    print(f"\nCategorizing {len(emails)} emails using GPT-4o-mini...")
    print("Note: GPT-4o-mini provides efficient and accurate categorization.")
    
    # Process in batches of 10
    batch_size = 10
    all_results = []
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(emails) + batch_size - 1)//batch_size}...")
        results = categorizer.batch_categorize_emails_for_account(batch, account)
        all_results.extend(results)
    
    # Group emails by category
    categorized: Dict[str, List[Dict[str, Any]]] = {}
    
    for i, result in enumerate(all_results):
        category = result["category"]
        if category not in categorized:
            categorized[category] = []
        
        email_with_result = emails[i].copy()
        email_with_result["_category"] = result["category"]
        email_with_result["_confidence"] = result["confidence"]
        email_with_result["_reasoning"] = result["reasoning"]
        
        categorized[category].append(email_with_result)
    
    # Print results
    print("\nCategorization Results:")
    print("=" * 50)
    
    for category, category_emails in categorized.items():
        print(f"\n{category}: {len(category_emails)} emails")
        
        if category_emails:
            print("-" * 30)
            for email in category_emails:
                print(f"  - From: {email.get('from', 'Unknown')}")
                print(f"    Subject: {email.get('subject', 'No Subject')}")
                print(f"    Confidence: {email.get('_confidence', 0)}%")
                print(f"    Reasoning: {email.get('_reasoning', '')[:100]}...")
                print()


if __name__ == "__main__":
    main()



