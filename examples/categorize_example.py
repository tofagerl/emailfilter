#!/usr/bin/env python3
"""Example script demonstrating how to use the OpenAI GPT-4o-mini based email categorization."""

import json
import os
from pprint import pprint
from typing import List, Dict, Any

from emailfilter import categorizer
from emailfilter.models import EmailAccount, Category

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
sample_file = os.path.join(script_dir, "sample_emails.json")

# Load sample emails
with open(sample_file, "r") as f:
    emails: List[Dict[str, str]] = json.load(f)

print("Categorizing emails using OpenAI GPT-4o-mini API...")
print("Note: GPT-4o-mini provides a good balance between accuracy and efficiency.")
print(f"Total emails: {len(emails)}")
print("-" * 50)

# Initialize the OpenAI client
try:
    # Try to get API key from environment variable
    categorizer.initialize_openai_client()
    print("Initialized OpenAI client from environment variable")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    print("Please set the OPENAI_API_KEY environment variable or provide a config file.")
    exit(1)

# Create a mock account with categories
account = EmailAccount(
    name="Example Account",
    email_address="example@example.com",
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

# Categorize emails in a batch
print("\nBatch categorization example:")
print("-" * 50)

try:
    # Categorize all emails in one batch
    results = categorizer.batch_categorize_emails_for_account(emails, account)
    
    # Print results
    for i, result in enumerate(results):
        print(f"\nEmail {i+1}: {emails[i]['subject']}")
        print(f"From: {emails[i]['from']}")
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']}%")
        print(f"Reasoning: {result['reasoning']}")
        print("-" * 30)
except Exception as e:
    print(f"Error in batch categorization: {e}")

# Group emails by category
print("\n\nEmails grouped by category:")
print("-" * 50)

try:
    # Create a dictionary to store emails by category
    emails_by_category: Dict[str, List[Dict[str, str]]] = {}
    
    # Group emails by category
    for i, result in enumerate(results):
        category = result["category"]
        if category not in emails_by_category:
            emails_by_category[category] = []
        emails_by_category[category].append(emails[i])
    
    # Print emails by category
    for category, category_emails in emails_by_category.items():
        print(f"\nCategory: {category}")
        print(f"Count: {len(category_emails)}")
        for email in category_emails:
            print(f"  - {email['subject']}")
except Exception as e:
    print(f"Error grouping emails by category: {e}")

print("\nNote: To use this example, you need to set the OPENAI_API_KEY environment variable.") 