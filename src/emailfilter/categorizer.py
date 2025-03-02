"""Email categorization using OpenAI API."""

import os
import logging
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Any

import openai
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Create a file handler for detailed logs
os.makedirs('logs', exist_ok=True)
file_handler = logging.FileHandler('logs/openai_interactions.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class EmailCategory(Enum):
    """Email categories."""
    SPAM = auto()
    RECEIPTS = auto()
    PROMOTIONS = auto()
    UPDATES = auto()
    INBOX = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


# Global client
client = None


def load_api_key() -> None:
    """Load OpenAI API key from environment variables."""
    global client
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key not found in environment variables")
        raise ValueError(
            "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."
        )
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI API key loaded successfully")


def set_api_key(api_key: str) -> None:
    """Set the OpenAI API key."""
    global client
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI API key set manually")


def log_openai_interaction(email: Dict[str, str], prompt: str, response: str, category_result: str) -> None:
    """
    Log OpenAI API interaction to a file.
    
    Args:
        email: Email dictionary with keys like 'subject', 'from', 'body', etc.
        prompt: The prompt sent to OpenAI
        response: The response received from OpenAI
        category_result: The category result (as string)
    """
    try:
        # Log to the application logger
        logger.info(f"OpenAI categorized email '{email.get('subject', 'No Subject')}' as: {category_result}")
        
        # Create a more detailed log entry in a separate file
        with open('logs/detailed_openai_logs.jsonl', 'a') as f:
            import json
            from datetime import datetime
            
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'email_from': email.get('from', ''),
                'email_to': email.get('to', ''),
                'email_subject': email.get('subject', ''),
                'email_date': email.get('date', ''),
                'prompt_sent': prompt,
                'response_received': response,
                'category_result': category_result
            }
            
            # Don't log the full email body to avoid storing sensitive information
            # Just log a truncated version for context
            body = email.get('body', '')
            if body:
                log_entry['email_body_preview'] = body[:200] + ('...' if len(body) > 200 else '')
            
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        logger.error(f"Error logging OpenAI interaction: {e}")


def categorize_email(email: Dict[str, str]) -> EmailCategory:
    """
    Categorize a single email using OpenAI API.
    
    Args:
        email: Email dictionary with keys like 'subject', 'from', 'body', etc.
        
    Returns:
        EmailCategory: The predicted category for the email
    """
    # Ensure API key is loaded
    global client
    if not client:
        logger.debug("API key not set, loading from environment")
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
    
    logger.info(f"Categorizing email: {email.get('subject', 'No Subject')}")
    
    try:
        # Call the OpenAI API with GPT-4o-mini
        logger.debug("Sending request to OpenAI API")
        response = client.chat.completions.create(
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
        logger.info(f"OpenAI categorized email as: {category_text}")
        
        # Map the response to our enum
        category_map = {
            "SPAM": EmailCategory.SPAM,
            "RECEIPTS": EmailCategory.RECEIPTS,
            "PROMOTIONS": EmailCategory.PROMOTIONS,
            "UPDATES": EmailCategory.UPDATES,
            "INBOX": EmailCategory.INBOX
        }
        
        # Default to INBOX if the response doesn't match any category
        category = EmailCategory.INBOX
        for key, value in category_map.items():
            if key in category_text:
                category = value
                break
        
        # Log the interaction
        log_openai_interaction(
            email=email,
            prompt=prompt,
            response=response.choices[0].message.content,
            category_result=category.name
        )
        
        return category
    
    except Exception as e:
        logger.error(f"Error categorizing email: {e}")
        # Log the error
        log_openai_interaction(
            email=email,
            prompt=prompt,
            response=f"ERROR: {str(e)}",
            category_result="ERROR"
        )
        # Default to INBOX for errors
        return EmailCategory.INBOX


def categorize_email_with_custom_categories(
    email: Dict[str, str], 
    categories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Categorize a single email using OpenAI API with custom categories.
    
    Args:
        email: Email dictionary with keys like 'subject', 'from', 'body', etc.
        categories: List of category dictionaries with keys 'id', 'name', and 'description'
        
    Returns:
        Dict: The predicted category dictionary with 'id', 'name', and 'description'
    """
    # Ensure API key is loaded
    if not client:
        logger.debug("API key not set, loading from environment")
        load_api_key()
    
    # Prepare the email content for the API
    email_content = f"""
    From: {email.get('from', 'Unknown')}
    To: {email.get('to', 'Unknown')}
    Subject: {email.get('subject', 'No Subject')}
    Date: {email.get('date', 'Unknown')}
    
    {email.get('body', 'No Body')}
    """
    
    # Create category descriptions for the prompt
    category_descriptions = []
    for category in categories:
        description = category.get('description', '')
        if description:
            category_descriptions.append(f"- {category['name']}: {description}")
        else:
            category_descriptions.append(f"- {category['name']}")
    
    category_text = "\n".join(category_descriptions)
    
    # Define the prompt for the API
    prompt = f"""
    Categorize the following email into exactly one of these categories:
    {category_text}
    
    Email:
    {email_content}
    
    Category:
    """
    
    logger.info(f"Categorizing email with custom categories: {email.get('subject', 'No Subject')}")
    
    try:
        # Call the OpenAI API with GPT-4o-mini
        logger.debug("Sending request to OpenAI API with custom categories")
        response = client.chat.completions.create(
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
        logger.info(f"OpenAI categorized email as: {category_text}")
        
        # Map the response to our categories
        # First try exact match
        selected_category = None
        for category in categories:
            if category['name'].upper() == category_text:
                selected_category = category
                break
        
        # Then try partial match
        if not selected_category:
            for category in categories:
                if category['name'].upper() in category_text:
                    selected_category = category
                    break
        
        # Default to the first category with name "INBOX" if it exists
        if not selected_category:
            for category in categories:
                if category['name'].upper() == "INBOX":
                    selected_category = category
                    break
        
        # Otherwise, return the first category
        if not selected_category:
            selected_category = categories[0] if categories else {"id": 0, "name": "INBOX", "description": "Default category"}
        
        # Log the interaction
        log_openai_interaction(
            email=email,
            prompt=prompt,
            response=response.choices[0].message.content,
            category_result=selected_category['name']
        )
        
        return selected_category
    
    except Exception as e:
        logger.error(f"Error categorizing email with custom categories: {e}")
        # Log the error
        log_openai_interaction(
            email=email,
            prompt=prompt,
            response=f"ERROR: {str(e)}",
            category_result="ERROR"
        )
        # Default to first category for errors
        return categories[0] if categories else {"id": 0, "name": "INBOX", "description": "Default category"}


def batch_categorize_emails(
    emails: List[Dict[str, str]], 
    batch_size: int = 10
) -> List[Dict[str, Any]]:
    """
    Categorize a batch of emails using OpenAI API.
    
    Args:
        emails: List of email dictionaries
        batch_size: Number of emails to process in each batch
        
    Returns:
        List[Dict]: List of dictionaries with 'email' and 'category' keys
    """
    results = []
    
    logger.info(f"Batch categorizing {len(emails)} emails")
    
    for i, email in enumerate(emails):
        try:
            logger.debug(f"Processing email {i+1}/{len(emails)}")
            category = categorize_email(email)
            results.append({
                "email": email,
                "category": category.name.lower()
            })
        except Exception as e:
            logger.error(f"Error categorizing email: {e}")
            # Default to INBOX for errors
            results.append({
                "email": email,
                "category": EmailCategory.INBOX.name.lower()
            })
    
    logger.info(f"Completed batch categorization of {len(emails)} emails")
    return results


def batch_categorize_emails_with_custom_categories(
    emails: List[Dict[str, str]], 
    categories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Categorize a batch of emails using OpenAI API with custom categories.
    
    Args:
        emails: List of email dictionaries
        categories: List of category dictionaries with keys 'id', 'name', and 'description'
        
    Returns:
        List[Dict]: List of dictionaries with 'email' and 'category' keys
    """
    results = []
    
    logger.info(f"Batch categorizing {len(emails)} emails with custom categories")
    
    for i, email in enumerate(emails):
        try:
            logger.debug(f"Processing email {i+1}/{len(emails)} with custom categories")
            category = categorize_email_with_custom_categories(email, categories)
            results.append({
                "email": email,
                "category": category
            })
        except Exception as e:
            logger.error(f"Error categorizing email with custom categories: {e}")
            # Default to first category for errors
            default_category = categories[0] if categories else {"id": 0, "name": "INBOX", "description": "Default category"}
            results.append({
                "email": email,
                "category": default_category
            })
    
    logger.info(f"Completed batch categorization of {len(emails)} emails with custom categories")
    return results


def categorize_and_filter(
    emails: List[Dict[str, str]]
) -> Dict[EmailCategory, List[Dict[str, str]]]:
    """
    Categorize emails and filter them based on categories.
    
    Args:
        emails: List of email dictionaries
        
    Returns:
        Dict[EmailCategory, List[Dict]]: Dictionary mapping categories to lists of emails
    """
    # Initialize result dictionary with empty lists for each category
    result = {category: [] for category in EmailCategory}
    
    logger.info(f"Categorizing and filtering {len(emails)} emails")
    
    # Categorize each email and add it to the appropriate list
    for i, email in enumerate(emails):
        try:
            logger.debug(f"Processing email {i+1}/{len(emails)}")
            category = categorize_email(email)
            result[category].append(email)
        except Exception as e:
            logger.error(f"Error categorizing email: {e}")
            # Default to INBOX for errors
            result[EmailCategory.INBOX].append(email)
    
    logger.info(f"Completed categorization and filtering of {len(emails)} emails")
    return result


def categorize_and_filter_with_custom_categories(
    emails: List[Dict[str, str]], 
    categories: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, str]]]:
    """
    Categorize emails with custom categories and filter them based on categories.
    
    Args:
        emails: List of email dictionaries
        categories: List of category dictionaries with keys 'id', 'name', and 'description'
        
    Returns:
        Dict[str, List[Dict]]: Dictionary mapping category names to lists of emails
    """
    # Initialize result dictionary with empty lists for each category
    result = {category['name']: [] for category in categories}
    
    logger.info(f"Categorizing and filtering {len(emails)} emails with custom categories")
    
    # Categorize each email and add it to the appropriate list
    for i, email in enumerate(emails):
        try:
            logger.debug(f"Processing email {i+1}/{len(emails)} with custom categories")
            category = categorize_email_with_custom_categories(email, categories)
            result[category['name']].append(email)
        except Exception as e:
            logger.error(f"Error categorizing email with custom categories: {e}")
            # Default to first category for errors
            default_category_name = categories[0]['name'] if categories else "INBOX"
            result[default_category_name].append(email)
    
    logger.info(f"Completed categorization and filtering of {len(emails)} emails with custom categories")
    return result


def cleanup_old_logs(max_age_days: int = 7) -> int:
    """
    Clean up old log files.
    
    Args:
        max_age_days: Maximum age of log files in days
        
    Returns:
        int: Number of deleted log entries
    """
    try:
        import os
        import time
        from datetime import datetime, timedelta
        
        log_file = 'logs/detailed_openai_logs.jsonl'
        if not os.path.exists(log_file):
            return 0
        
        # Get the current time
        now = datetime.utcnow()
        cutoff_date = now - timedelta(days=max_age_days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        # Read the log file and filter out old entries
        import json
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        deleted_count = 0
        
        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get('timestamp', '') >= cutoff_timestamp:
                    new_lines.append(line)
                else:
                    deleted_count += 1
            except json.JSONDecodeError:
                # Keep lines that can't be parsed as JSON
                new_lines.append(line)
        
        # Write the filtered entries back to the file
        with open(log_file, 'w') as f:
            f.writelines(new_lines)
        
        logger.info(f"Cleaned up {deleted_count} old log entries")
        return deleted_count
    
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}")
        return 0 