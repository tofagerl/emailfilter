"""Email categorization using OpenAI API."""

import os
import logging
import yaml
import json
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

import openai
from openai import OpenAI

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Get logs directory from environment variable or use default
logs_dir = os.environ.get('EMAILFILTER_LOGS_DIR', 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Create a file handler for detailed logs
file_handler = logging.FileHandler(os.path.join(logs_dir, 'openai_interactions.log'))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Global client
client = None

def load_api_key(config_path: str = "config.yaml") -> None:
    """Load OpenAI API key from config file.
    
    Args:
        config_path: Path to the config file
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        api_key = config.get("openai_api_key")
        if not api_key:
            raise ValueError("OpenAI API key not found in config file")
        
        set_api_key(api_key)
    except Exception as e:
        logger.error(f"Error loading API key: {e}")
        raise

def set_api_key(api_key: str) -> None:
    """Set the OpenAI API key.
    
    Args:
        api_key: The OpenAI API key
    """
    global client
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI API key set")

def log_openai_interaction(email: Dict[str, str], prompt: str, response: str, category_result: str) -> None:
    """Log OpenAI API interaction for debugging.
    
    Args:
        email: The email that was categorized
        prompt: The prompt sent to OpenAI
        response: The response from OpenAI
        category_result: The final category assigned
    """
    try:
        # Create log entry with more detailed email information
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "email_subject": email.get("subject", ""),
            "email_from": email.get("from", ""),
            "email_to": email.get("to", ""),
            "email_date": email.get("date", ""),
            "prompt": prompt,
            "response": response,
            "category": category_result
        }
        
        # Write to log file
        log_file = os.path.join(logs_dir, f"categorization_{datetime.now().strftime('%Y-%m-%d')}.log")
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        # Log a summary to the application log
        logger.info(
            f"Categorized email: "
            f"From: {email.get('from', '')[:40]}... | "
            f"To: {email.get('to', '')[:40]}... | "
            f"Subject: {email.get('subject', '')[:40]}... | "
            f"Category: {category_result}"
        )
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")

def batch_categorize_emails_for_account(
    emails: List[Dict[str, str]], 
    account,
    batch_size: int = 10,
    model: str = "gpt-4o-mini"
) -> List[Dict[str, Any]]:
    """Categorize a batch of emails for a specific account.
    
    Args:
        emails: List of email dictionaries
        account: The EmailAccount object with category definitions
        batch_size: Maximum number of emails to categorize in one batch
        model: The OpenAI model to use for categorization
        
    Returns:
        List of dictionaries with categorization results
    """
    if not emails:
        return []
    
    # Get all available categories for this account
    categories = account.categories
    category_info = []
    for category in categories:
        category_info.append({
            "name": category.name,
            "description": category.description,
            "folder": category.foldername
        })
    
    # Prepare system prompt
    system_prompt = f"""You are an email categorization assistant. Your task is to categorize emails into one of the following categories:

{json.dumps(category_info, indent=2)}

For each email, respond with a JSON object containing:
1. "category": The category name (must be one of: {', '.join([c.name for c in categories])})
2. "confidence": Your confidence level (0-100)
3. "reasoning": Brief explanation of your categorization

Analyze the email's subject, sender, and content to determine the most appropriate category.
Use the category descriptions to guide your decision.
"""
    
    # Prepare user prompt
    user_prompt = "Categorize the following emails:\n\n"
    for i, email in enumerate(emails[:batch_size]):
        user_prompt += f"Email {i+1}:\n"
        user_prompt += f"From: {email.get('from', '')}\n"
        user_prompt += f"To: {email.get('to', '')}\n"
        user_prompt += f"Subject: {email.get('subject', '')}\n"
        user_prompt += f"Date: {email.get('date', '')}\n"
        user_prompt += f"Body: {email.get('body', '')[:1000]}...\n\n"
    
    try:
        # Call OpenAI API with the specified model
        response = client.chat.completions.create(
            model=model,  # Use the model from configuration
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        # Parse response
        response_text = response.choices[0].message.content
        
        # Log interaction for debugging
        for i, email in enumerate(emails[:batch_size]):
            log_openai_interaction(
                email, 
                f"Batch categorization with {model} (email {i+1} of {len(emails[:batch_size])})", 
                response_text, 
                "See full response"
            )
        
        # Extract JSON objects from response
        results = []
        try:
            # Try to parse as a JSON array
            import re
            json_objects = re.findall(r'\{[^{}]*\}', response_text)
            
            # Get valid category names (uppercase for case-insensitive comparison)
            valid_categories = [c.name.upper() for c in categories]
            
            for json_obj in json_objects:
                try:
                    result = json.loads(json_obj)
                    # Ensure category is valid
                    if "category" in result:
                        category = result["category"].upper()
                        if category in valid_categories:
                            result["category"] = category
                        else:
                            # Default to INBOX if category is invalid
                            logger.warning(f"Invalid category: {category}, defaulting to INBOX")
                            result["category"] = "INBOX"
                    else:
                        result["category"] = "INBOX"
                    
                    results.append(result)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON object: {json_obj}")
                    results.append({"category": "INBOX", "confidence": 0, "reasoning": "Failed to parse response"})
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            # Fallback: create default results
            results = [{"category": "INBOX", "confidence": 0, "reasoning": "Failed to parse response"}] * len(emails[:batch_size])
        
        # Ensure we have a result for each email
        while len(results) < len(emails[:batch_size]):
            results.append({"category": "INBOX", "confidence": 0, "reasoning": "Missing from response"})
        
        return results
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        # Fallback: categorize all as inbox
        return [{"category": "INBOX", "confidence": 0, "reasoning": f"API error: {str(e)}"}] * len(emails[:batch_size])

# Default categories if not specified in config
DEFAULT_CATEGORIES = ["SPAM", "RECEIPTS", "PROMOTIONS", "UPDATES", "INBOX"]

# Dynamic EmailCategory enum creation
def create_email_category_enum(categories=None):
    """Create a dynamic EmailCategory enum with the given categories.
    
    Args:
        categories: List of category names (strings)
        
    Returns:
        An Enum class with the specified categories
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES
    
    # Ensure all categories are uppercase
    categories = [cat.upper() for cat in categories]
    
    # Create enum items dictionary
    enum_items = {category: auto() for category in categories}
    
    # Create the Enum class
    EmailCategory = Enum('EmailCategory', enum_items)
    
    # Add __str__ method to the Enum class
    def __str__(self):
        return self.name.capitalize()
    
    EmailCategory.__str__ = __str__
    
    return EmailCategory

# Initialize with default categories, will be updated when config is loaded
EmailCategory = create_email_category_enum()

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
    """Categorize a batch of emails.
    
    Args:
        emails: List of email dictionaries
        batch_size: Maximum number of emails to categorize in one batch
        
    Returns:
        List of dictionaries with categorization results
    """
    if not emails:
        return []
    
    # Get all available categories
    available_categories = [category.name.lower() for category in EmailCategory]
    
    # Prepare system prompt
    system_prompt = f"""You are an email categorization assistant. Your task is to categorize emails into one of the following categories:
{', '.join(available_categories)}

For each email, respond with a JSON object containing:
1. "category": The category name (must be one of: {', '.join(available_categories)})
2. "confidence": Your confidence level (0-100)
3. "reasoning": Brief explanation of your categorization

Analyze the email's subject, sender, and content to determine the most appropriate category.
"""
    
    # Prepare user prompt
    user_prompt = "Categorize the following emails:\n\n"
    for i, email in enumerate(emails[:batch_size]):
        user_prompt += f"Email {i+1}:\n"
        user_prompt += f"From: {email.get('from', '')}\n"
        user_prompt += f"To: {email.get('to', '')}\n"
        user_prompt += f"Subject: {email.get('subject', '')}\n"
        user_prompt += f"Date: {email.get('date', '')}\n"
        user_prompt += f"Body: {email.get('body', '')[:1000]}...\n\n"
    
    try:
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        # Parse response
        response_text = response.choices[0].message.content
        
        # Log interaction for debugging
        for i, email in enumerate(emails[:batch_size]):
            log_openai_interaction(
                email, 
                f"Batch categorization (email {i+1} of {len(emails[:batch_size])})", 
                response_text, 
                "See full response"
            )
        
        # Extract JSON objects from response
        results = []
        try:
            # Try to parse as a JSON array
            import re
            json_objects = re.findall(r'\{[^{}]*\}', response_text)
            
            for json_obj in json_objects:
                try:
                    result = json.loads(json_obj)
                    # Ensure category is lowercase and valid
                    if "category" in result:
                        category = result["category"].lower()
                        if category in available_categories:
                            result["category"] = category
                        else:
                            # Default to inbox if category is invalid
                            logger.warning(f"Invalid category: {category}, defaulting to inbox")
                            result["category"] = "inbox"
                    else:
                        result["category"] = "inbox"
                    
                    results.append(result)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON object: {json_obj}")
                    results.append({"category": "inbox", "confidence": 0, "reasoning": "Failed to parse response"})
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            # Fallback: create default results
            results = [{"category": "inbox", "confidence": 0, "reasoning": "Failed to parse response"}] * len(emails[:batch_size])
        
        # Ensure we have a result for each email
        while len(results) < len(emails[:batch_size]):
            results.append({"category": "inbox", "confidence": 0, "reasoning": "Missing from response"})
        
        return results
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        # Fallback: categorize all as inbox
        return [{"category": "inbox", "confidence": 0, "reasoning": f"API error: {str(e)}"}] * len(emails[:batch_size])

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
    Clean up old log entries.
    
    Args:
        max_age_days: Maximum age of log entries in days
        
    Returns:
        Number of deleted log entries
    """
    try:
        log_file = os.path.join(logs_dir, 'detailed_openai_logs.jsonl')
        
        if not os.path.exists(log_file):
            logger.info(f"Log file not found: {log_file}")
            return 0
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # Read existing logs
        with open(log_file, 'r') as f:
            logs = [json.loads(line) for line in f if line.strip()]
        
        # Filter logs by date
        old_count = len(logs)
        logs = [
            log for log in logs 
            if datetime.fromisoformat(log.get("timestamp", "2000-01-01")) > cutoff_date
        ]
        new_count = len(logs)
        deleted_count = old_count - new_count
        
        # Write back filtered logs
        with open(log_file, 'w') as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")
        
        logger.info(f"Cleaned up {deleted_count} log entries older than {max_age_days} days")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
        return 0 