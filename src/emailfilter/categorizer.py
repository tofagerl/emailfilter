"""Email categorization using OpenAI API."""

import os
import logging
import yaml
import json
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import warnings

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

def initialize_openai_client(api_key: str = None, config_path: str = None) -> None:
    """Initialize the OpenAI client with an API key.
    
    Args:
        api_key: The OpenAI API key (optional)
        config_path: Path to a config file containing the API key (optional)
        
    Raises:
        ValueError: If neither api_key nor config_path is provided, or if the API key is not found
    """
    global client
    
    # If API key is provided directly, use it
    if api_key:
        client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized with provided API key")
        return
    
    # If config path is provided, try to load the API key from it
    if config_path:
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            
            config_api_key = config.get("openai_api_key")
            if not config_api_key:
                raise ValueError("OpenAI API key not found in config file")
            
            client = OpenAI(api_key=config_api_key)
            logger.info("OpenAI client initialized with API key from config file")
            return
        except Exception as e:
            logger.error(f"Error loading API key from config: {e}")
            raise
    
    # Try to get API key from environment variable
    env_api_key = os.environ.get("OPENAI_API_KEY")
    if env_api_key:
        client = OpenAI(api_key=env_api_key)
        logger.info("OpenAI client initialized with API key from environment variable")
        return
    
    # If we get here, we couldn't initialize the client
    raise ValueError(
        "Could not initialize OpenAI client. Please provide an API key directly, "
        "through a config file, or set the OPENAI_API_KEY environment variable."
    )

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

def prepare_category_info(account) -> List[Dict[str, str]]:
    """Extract category information from an account.
    
    Args:
        account: The EmailAccount object with category definitions
        
    Returns:
        List of dictionaries with category information
    """
    categories = account.categories
    category_info = []
    for category in categories:
        category_info.append({
            "name": category.name,
            "description": category.description,
            "folder": category.foldername
        })
    return category_info

def create_system_prompt(category_info: List[Dict[str, str]], categories) -> str:
    """Create the system prompt for the OpenAI API.
    
    Args:
        category_info: List of dictionaries with category information
        categories: List of Category objects
        
    Returns:
        System prompt string
    """
    return f"""You are an email categorization assistant. Your task is to categorize emails into one of the following categories:

{json.dumps(category_info, indent=2)}

For each email, respond with a JSON object containing:
1. "category": The category name (must be one of: {', '.join([c.name for c in categories])})
2. "confidence": Your confidence level (0-100)
3. "reasoning": Brief explanation of your categorization

Analyze the email's subject, sender, and content to determine the most appropriate category.
Use the category descriptions to guide your decision.
"""

def create_user_prompt(emails: List[Dict[str, str]], batch_size: int) -> str:
    """Create the user prompt for the OpenAI API.
    
    Args:
        emails: List of email dictionaries
        batch_size: Maximum number of emails to include
        
    Returns:
        User prompt string
    """
    user_prompt = "Categorize the following emails:\n\n"
    for i, email in enumerate(emails[:batch_size]):
        user_prompt += f"Email {i+1}:\n"
        user_prompt += f"From: {email.get('from', '')}\n"
        user_prompt += f"To: {email.get('to', '')}\n"
        user_prompt += f"Subject: {email.get('subject', '')}\n"
        user_prompt += f"Date: {email.get('date', '')}\n"
        user_prompt += f"Body: {email.get('body', '')[:1000]}...\n\n"
    return user_prompt

def call_openai_api(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call the OpenAI API with the given prompts.
    
    Args:
        system_prompt: The system prompt
        user_prompt: The user prompt
        model: The OpenAI model to use
        
    Returns:
        The response text from OpenAI
        
    Raises:
        Exception: If there's an error calling the API
    """
    global client
    if not client:
        raise ValueError("OpenAI client not initialized. Call initialize_openai_client() first.")
    
    response = client.chat.completions.create(
        model=model,
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
    
    return response.choices[0].message.content

def extract_json_objects(response_text: str) -> List[str]:
    """Extract JSON objects from a text response.
    
    Args:
        response_text: The text containing JSON objects
        
    Returns:
        List of JSON object strings
    """
    import re
    return re.findall(r'\{[^{}]*\}', response_text)

def validate_and_normalize_category(result: Dict[str, Any], valid_categories: List[str]) -> Dict[str, Any]:
    """Validate and normalize a category in a result.
    
    Args:
        result: The result dictionary
        valid_categories: List of valid category names (uppercase)
        
    Returns:
        The validated and normalized result dictionary
    """
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
    
    return result

def parse_openai_response(response_text: str, categories, batch_size: int) -> List[Dict[str, Any]]:
    """Parse the OpenAI API response.
    
    Args:
        response_text: The response text from OpenAI
        categories: List of Category objects
        batch_size: The batch size used for the request
        
    Returns:
        List of dictionaries with categorization results
    """
    results = []
    try:
        # Extract JSON objects from response
        json_objects = extract_json_objects(response_text)
        
        # Get valid category names (uppercase for case-insensitive comparison)
        valid_categories = [c.name.upper() for c in categories]
        
        for json_obj in json_objects:
            try:
                result = json.loads(json_obj)
                result = validate_and_normalize_category(result, valid_categories)
                results.append(result)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON object: {json_obj}")
                results.append({"category": "INBOX", "confidence": 0, "reasoning": "Failed to parse response"})
    except Exception as e:
        logger.error(f"Error parsing response: {e}")
        # Fallback: create default results
        results = [{"category": "INBOX", "confidence": 0, "reasoning": "Failed to parse response"}] * batch_size
    
    # Ensure we have a result for each email
    while len(results) < batch_size:
        results.append({"category": "INBOX", "confidence": 0, "reasoning": "Missing from response"})
    
    return results

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
    
    # Limit batch size to the number of emails
    actual_batch_size = min(batch_size, len(emails))
    
    try:
        # Prepare category information
        category_info = prepare_category_info(account)
        
        # Create prompts
        system_prompt = create_system_prompt(category_info, account.categories)
        user_prompt = create_user_prompt(emails, actual_batch_size)
        
        # Call OpenAI API
        response_text = call_openai_api(system_prompt, user_prompt, model)
        
        # Parse response
        results = parse_openai_response(response_text, account.categories, actual_batch_size)
        
        # Log interaction for debugging with actual categories
        for i, email in enumerate(emails[:actual_batch_size]):
            if i < len(results):
                category_result = results[i]["category"]
                log_openai_interaction(
                    email, 
                    f"Batch categorization with {model} (email {i+1} of {actual_batch_size})", 
                    response_text, 
                    category_result
                )
        
        return results
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        # Fallback: categorize all as inbox
        fallback_results = [{"category": "INBOX", "confidence": 0, "reasoning": f"API error: {str(e)}"}] * actual_batch_size
        
        # Log the fallback categorization
        for i, email in enumerate(emails[:actual_batch_size]):
            log_openai_interaction(
                email,
                f"Batch categorization with {model} failed (email {i+1} of {actual_batch_size})",
                f"Error: {str(e)}",
                "INBOX"
            )
        
        return fallback_results

# For backward compatibility with tests and examples
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

# Initialize with default categories for backward compatibility
EmailCategory = create_email_category_enum()

def cleanup_old_logs(max_age_days: int = 7) -> int:
    """Clean up old log files.
    
    Args:
        max_age_days: Maximum age of log files in days
        
    Returns:
        Number of files deleted
    """
    try:
        # Get current time
        now = datetime.now()
        cutoff_date = now - timedelta(days=max_age_days)
        
        # Get list of log files
        log_files = [f for f in os.listdir(logs_dir) if f.startswith("categorization_")]
        
        # Delete old files
        deleted_count = 0
        for file_name in log_files:
            try:
                # Extract date from filename
                date_str = file_name.replace("categorization_", "").replace(".log", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Check if file is older than cutoff date
                if file_date < cutoff_date:
                    os.remove(os.path.join(logs_dir, file_name))
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error processing log file {file_name}: {e}")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}")
        return 0 