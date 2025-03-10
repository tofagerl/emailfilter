#!/usr/bin/env python
"""Test script to demonstrate the logging functionality."""

import os
import json
import logging
from dotenv import load_dotenv

from emailfilter.categorizer import (
    initialize_openai_client, batch_categorize_emails_for_account,
    cleanup_old_logs
)
from emailfilter.models import EmailAccount, Category

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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
    
    # Test with default categories
    logger.info("Testing categorization with default categories")
    results = batch_categorize_emails_for_account([test_email], default_account)
    logger.info(f"Email categorized as: {results[0]['category']}")
    
    # Test with custom categories
    logger.info("Testing categorization with custom categories")
    custom_account = EmailAccount(
        name="Custom Account",
        email_address="custom@example.com",
        password="password",
        imap_server="imap.example.com",
        categories=[
            Category("SPAM", "Unwanted, unsolicited emails that might be scams or junk", "[Spam]"),
            Category("MARKETING", "Promotional emails, offers, and advertisements", "[Marketing]"),
            Category("IMPORTANT", "Critical emails that need immediate attention", "INBOX"),
            Category("NEWSLETTERS", "Regular updates and newsletters", "[Newsletters]"),
            Category("PERSONAL", "Personal communications from friends and family", "[Personal]")
        ]
    )
    
    custom_results = batch_categorize_emails_for_account([test_email], custom_account)
    logger.info(f"Email categorized with custom categories as: {custom_results[0]['category']}")
    
    # View the log file
    logger.info("Checking log file")
    try:
        log_files = [f for f in os.listdir('logs') if f.startswith('categorization_')]
        if log_files:
            latest_log = os.path.join('logs', sorted(log_files)[-1])
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                logger.info(f"Found {len(lines)} log entries in {latest_log}")
                
                # Display the most recent log entry
                if lines:
                    latest_entry = json.loads(lines[-1])
                    logger.info("Latest log entry:")
                    logger.info(f"  Timestamp: {latest_entry.get('timestamp', '')}")
                    logger.info(f"  Email Subject: {latest_entry.get('email_subject', '')}")
                    logger.info(f"  Category: {latest_entry.get('category', '')}")
        else:
            logger.warning("No log files found")
    except FileNotFoundError:
        logger.error("Logs directory not found")
    except Exception as e:
        logger.error(f"Error reading log files: {e}")
    
    # Clean up old logs
    logger.info("Cleaning up old logs")
    deleted_count = cleanup_old_logs()
    logger.info(f"Cleaned up {deleted_count} old log entries")

if __name__ == "__main__":
    main() 