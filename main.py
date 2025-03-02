#!/usr/bin/env python3
"""
Email Filter - A Python application for filtering and processing emails.

This is a simple entry point that demonstrates the OpenAI GPT-4o-mini based email categorization.
"""

import json
import os
import sys
from typing import Dict, List

from emailfilter import categorizer


def main() -> None:
    """Main entry point for the application."""
    print("Email Filter - OpenAI GPT-4o-mini powered Email Categorization")
    print("=" * 50)
    
    # Check if OpenAI API key is set
    try:
        categorizer.load_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease set your OpenAI API key in the .env file or as an environment variable:")
        print("  OPENAI_API_KEY=your_api_key_here")
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
    
    # Categorize emails
    print(f"\nCategorizing {len(emails)} emails using GPT-4o-mini...")
    print("Note: GPT-4o-mini provides efficient and accurate categorization.")
    categorized: Dict[str, List[Dict[str, str]]] = {
        str(category): [] for category in categorizer.EmailCategory
    }
    
    for i, email in enumerate(emails, 1):
        print(f"Processing email {i}/{len(emails)}...")
        category = categorizer.categorize_email(email)
        categorized[str(category)].append(email)
    
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
                print()


if __name__ == "__main__":
    main()



