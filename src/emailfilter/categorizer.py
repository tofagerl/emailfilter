"""Email categorization using OpenAI API."""

import os
from enum import Enum, auto
from typing import Dict, List, Optional, Union

import openai
from dotenv import load_dotenv


class EmailCategory(Enum):
    """Email categories."""
    SPAM = auto()
    RECEIPTS = auto()
    PROMOTIONS = auto()
    UPDATES = auto()
    INBOX = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


def load_api_key() -> None:
    """Load OpenAI API key from environment variables."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."
        )
    openai.api_key = api_key


def categorize_email(email: Dict[str, str]) -> EmailCategory:
    """
    Categorize a single email using OpenAI API.
    
    Args:
        email: Email dictionary with keys like 'subject', 'from', 'body', etc.
        
    Returns:
        EmailCategory: The predicted category for the email
    """
    # Ensure API key is loaded
    if not openai.api_key:
        load_api_key()
    
    # Prepare the email content for the API
    email_content = f"""
    From: {email.get('from', 'Unknown')}
    To: {email.get('to', 'Unknown')}
    Subject: {email.get('subject', 'No Subject')}
    Date: {email.get('date', 'Unknown')}
    
    {email.get('body', 'No Body')}
    """
    
    # Define the prompt for the API
    prompt = f"""
    Categorize the following email into exactly one of these categories:
    - Spam: Unwanted, unsolicited emails that might be scams or junk
    - Receipts: Transaction confirmations, receipts, order updates
    - Promotions: Marketing emails, newsletters, offers, discounts
    - Updates: Non-urgent notifications, social media updates, news
    - Inbox: Important emails that need attention or quick response
    
    Email:
    {email_content}
    
    Category:
    """
    
    # Call the OpenAI API with GPT-4o-mini
    response = openai.chat.completions.create(
        model="gpt-4o-mini",  # Using GPT-4o-mini for efficient categorization
        messages=[
            {"role": "system", "content": "You are an email categorization assistant. Categorize the email into exactly one of the specified categories."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=10,
        temperature=0.2  # Lower temperature for more consistent results
    )
    
    # Extract and parse the category from the response
    category_text = response.choices[0].message.content.strip().upper()
    
    # Map the response to our enum
    category_map = {
        "SPAM": EmailCategory.SPAM,
        "RECEIPTS": EmailCategory.RECEIPTS,
        "PROMOTIONS": EmailCategory.PROMOTIONS,
        "UPDATES": EmailCategory.UPDATES,
        "INBOX": EmailCategory.INBOX
    }
    
    # Default to INBOX if the response doesn't match any category
    for key, value in category_map.items():
        if key in category_text:
            return value
    
    return EmailCategory.INBOX


def batch_categorize_emails(
    emails: List[Dict[str, str]], 
    batch_size: int = 10
) -> List[Dict[str, Union[Dict[str, str], str]]]:
    """
    Categorize a batch of emails using OpenAI API.
    
    Args:
        emails: List of email dictionaries
        batch_size: Number of emails to process in each batch
        
    Returns:
        List of dictionaries with the email and its category
    """
    categorized_emails = []
    
    # Process emails in batches to avoid rate limits
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i+batch_size]
        
        for email in batch:
            category = categorize_email(email)
            categorized_emails.append({
                "email": email,
                "category": str(category)
            })
    
    return categorized_emails


def categorize_and_filter(
    emails: List[Dict[str, str]], 
    categories: Optional[List[EmailCategory]] = None
) -> Dict[EmailCategory, List[Dict[str, str]]]:
    """
    Categorize emails and filter them by category.
    
    Args:
        emails: List of email dictionaries
        categories: List of categories to include (None for all)
        
    Returns:
        Dictionary mapping categories to lists of emails
    """
    result: Dict[EmailCategory, List[Dict[str, str]]] = {
        category: [] for category in EmailCategory
    }
    
    for email in emails:
        category = categorize_email(email)
        if categories is None or category in categories:
            result[category].append(email)
    
    return result 