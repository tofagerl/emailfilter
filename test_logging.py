#!/usr/bin/env python
"""Test script to demonstrate the logging functionality."""

import os
import json
import logging
from dotenv import load_dotenv

from emailfilter.categorizer import (
    set_api_key, categorize_email, categorize_email_with_custom_categories,
    cleanup_old_logs
)

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
    
    # Set the API key
    set_api_key(api_key)
    
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
    
    # Test with default categories
    logger.info("Testing categorization with default categories")
    category = categorize_email(test_email)
    logger.info(f"Email categorized as: {category}")
    
    # Test with custom categories
    logger.info("Testing categorization with custom categories")
    custom_categories = [
        {"id": 1, "name": "SPAM", "description": "Unwanted, unsolicited emails that might be scams or junk"},
        {"id": 2, "name": "MARKETING", "description": "Promotional emails, offers, and advertisements"},
        {"id": 3, "name": "IMPORTANT", "description": "Critical emails that need immediate attention"},
        {"id": 4, "name": "NEWSLETTERS", "description": "Regular updates and newsletters"},
        {"id": 5, "name": "PERSONAL", "description": "Personal communications from friends and family"}
    ]
    
    custom_category = categorize_email_with_custom_categories(test_email, custom_categories)
    logger.info(f"Email categorized with custom categories as: {custom_category['name']}")
    
    # View the log file
    logger.info("Checking log file")
    try:
        with open('logs/detailed_openai_logs.jsonl', 'r') as f:
            lines = f.readlines()
            logger.info(f"Found {len(lines)} log entries")
            
            # Display the most recent log entry
            if lines:
                latest_entry = json.loads(lines[-1])
                logger.info("Latest log entry:")
                logger.info(f"  Timestamp: {latest_entry.get('timestamp', '')}")
                logger.info(f"  Email Subject: {latest_entry.get('email_subject', '')}")
                logger.info(f"  Category Result: {latest_entry.get('category_result', '')}")
    except FileNotFoundError:
        logger.error("Log file not found")
    
    # Clean up old logs
    logger.info("Cleaning up old logs")
    deleted_count = cleanup_old_logs()
    logger.info(f"Cleaned up {deleted_count} old log entries")

if __name__ == "__main__":
    main() 