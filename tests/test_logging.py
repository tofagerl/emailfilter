#!/usr/bin/env python
"""Test script to demonstrate the logging functionality."""

import os
import json
import logging
from dotenv import load_dotenv

from mailmind.categorizer import (
    initialize_openai_client, batch_categorize_emails_for_account
)
from mailmind.models import EmailAccount, Category

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the test script."""
    # Load environment variables
    load_dotenv()
    
    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return
    
    # Initialize the OpenAI client
    initialize_openai_client(api_key=api_key)
    
    # Create a test email
    test_email = {
        "from": "test@example.com",
        "to": "user@example.com",
        "subject": "Special Offer: 50% off all products!",
        "date": "2023-06-01",
        "body": """
        Dear valued customer,
        
        We're excited to offer you an exclusive 50% discount on all our products!
        This limited-time offer is only available for the next 24 hours.
        
        Visit our website at example.com/shop to browse our selection.
        
        Best regards,
        The Marketing Team
        """
    }
    
    # Create an account with default categories
    default_account = EmailAccount(
        name="Test Account",
        email_address="test@example.com",
        password="password",
        imap_server="imap.example.com",
        categories=[
            Category("SPAM", "Unwanted emails", "[Spam]"),
            Category("RECEIPTS", "Order confirmations", "[Receipts]"),
            Category("PROMOTIONS", "Marketing emails", "[Promotions]"),
            Category("UPDATES", "Notifications", "[Updates]"),
            Category("INBOX", "Important emails", "INBOX")
        ]
    )
    
    # Test categorization with default categories
    logger.debug("Testing categorization with default categories")
    results = batch_categorize_emails_for_account([test_email], default_account)
    logger.debug(f"Email categorized as: {results[0]['category']}")
    
    # Test categorization with custom categories
    logger.debug("Testing categorization with custom categories")
    
    # Create custom categories
    custom_categories = [
        Category("IMPORTANT", "Critical emails", "Important"),
        Category("NEWSLETTERS", "Regular newsletters", "Newsletters"),
        Category("SOCIAL", "Social media notifications", "Social"),
        Category("FINANCE", "Financial emails", "Finance"),
        Category("OTHER", "Other emails", "Other")
    ]
    
    # Create account with custom categories
    custom_account = EmailAccount(
        name="Test",
        email_address="test@example.com",
        password="",
        imap_server="",
        categories=custom_categories
    )
    
    custom_results = batch_categorize_emails_for_account([test_email], custom_account)
    logger.debug(f"Email categorized with custom categories as: {custom_results[0]['category']}")

if __name__ == "__main__":
    main() 