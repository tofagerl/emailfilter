#!/usr/bin/env python3
"""Example script demonstrating how to use the OpenAI GPT-4o-mini based email categorization."""

import json
import os
from pprint import pprint

from emailfilter import categorizer

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
sample_file = os.path.join(script_dir, "sample_emails.json")

# Load sample emails
with open(sample_file, "r") as f:
    emails = json.load(f)

print("Categorizing emails using OpenAI GPT-4o-mini API...")
print("Note: GPT-4o-mini provides a good balance between accuracy and efficiency.")
print(f"Total emails: {len(emails)}")
print("-" * 50)

# Categorize each email
for i, email in enumerate(emails, 1):
    print(f"\nEmail {i}: {email['subject']}")
    print(f"From: {email['from']}")
    
    try:
        category = categorizer.categorize_email(email)
        print(f"Category: {category}")
    except Exception as e:
        print(f"Error categorizing email: {e}")
    
    print("-" * 30)

# Demonstrate batch categorization
print("\n\nBatch categorization example:")
print("-" * 50)

try:
    categorized_emails = categorizer.batch_categorize_emails(emails[:2])
    for item in categorized_emails:
        print(f"Subject: {item['email']['subject']}")
        print(f"Category: {item['category']}")
        print("-" * 30)
except Exception as e:
    print(f"Error in batch categorization: {e}")

# Demonstrate categorize_and_filter
print("\n\nCategorize and filter example:")
print("-" * 50)

try:
    # Get only INBOX and UPDATES categories
    categories = [categorizer.EmailCategory.INBOX, categorizer.EmailCategory.UPDATES]
    filtered_by_category = categorizer.categorize_and_filter(emails[:3], categories)
    
    for category, category_emails in filtered_by_category.items():
        if category in categories:
            print(f"\nCategory: {category}")
            print(f"Count: {len(category_emails)}")
            for email in category_emails:
                print(f"  - {email['subject']}")
except Exception as e:
    print(f"Error in categorize_and_filter: {e}")

print("\nNote: To use this example, you need to set the OPENAI_API_KEY environment variable.") 