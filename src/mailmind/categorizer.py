"""Email categorization using OpenAI API."""

import os
import logging
import yaml
import json
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Any

import openai
from openai import OpenAI

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Default categories if not specified in config
DEFAULT_CATEGORIES = ["SPAM", "RECEIPTS", "PROMOTIONS", "UPDATES", "INBOX"]


class CategorizationError(Exception):
    """Base exception for categorization errors."""
    pass


class APIError(CategorizationError):
    """Error when calling the OpenAI API."""
    pass


class ConfigurationError(CategorizationError):
    """Error in the categorizer configuration."""
    pass


class CategorizerConfig:
    """Configuration for the EmailCategorizer."""
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        batch_size: int = 10,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0
    ):
        """Initialize the categorizer configuration.
        
        Args:
            model: The OpenAI model to use
            batch_size: Maximum number of emails to categorize in one batch
            temperature: Controls randomness in the model's output
            max_tokens: Maximum number of tokens to generate
            top_p: Controls diversity via nucleus sampling
            frequency_penalty: Penalizes repeated tokens
            presence_penalty: Penalizes repeated topics
        """
        self.model = model
        self.batch_size = batch_size
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty


class Category:
    """Represents an email category."""
    
    def __init__(self, name: str, description: str, folder_name: str = None):
        """Initialize a category.
        
        Args:
            name: The name of the category
            description: A description of what emails belong in this category
            folder_name: The name of the folder to move emails to (defaults to name)
        """
        self.name = name.upper()
        self.description = description
        self.folder_name = folder_name or name

    def __str__(self) -> str:
        """Return the category name as string representation."""
        return self.name


class EmailCategorizer:
    """Categorizes emails using OpenAI API."""
    
    def __init__(
        self,
        api_key: str = None,
        config_path: str = None,
        config: CategorizerConfig = None
    ):
        """Initialize the email categorizer.
        
        Args:
            api_key: The OpenAI API key (optional)
            config_path: Path to a config file containing the API key (optional)
            config: Configuration for the categorizer (optional)
            
        Raises:
            ConfigurationError: If the API key cannot be found
        """
        self.client = None
        self.config = config or CategorizerConfig()
        self._initialize_client(api_key, config_path)
    
    def _initialize_client(self, api_key: str = None, config_path: str = None) -> None:
        """Initialize the OpenAI client with an API key.
        
        Args:
            api_key: The OpenAI API key (optional)
            config_path: Path to a config file containing the API key (optional)
            
        Raises:
            ConfigurationError: If the API key cannot be found
        """
        # If API key is provided directly, use it
        if api_key:
            self.client = OpenAI(api_key=api_key)
            logger.debug("OpenAI client initialized with provided API key")
            return
        
        # If config path is provided, try to load the API key from it
        if config_path:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                config_api_key = config.get("openai_api_key")
                if not config_api_key:
                    raise ConfigurationError("OpenAI API key not found in config file")
                
                self.client = OpenAI(api_key=config_api_key)
                logger.debug("OpenAI client initialized with API key from config file")
                return
            except Exception as e:
                logger.error(f"Error loading API key from config: {e}")
                raise ConfigurationError(f"Error loading API key from config: {e}")
        
        # Try to get API key from environment variable
        env_api_key = os.environ.get("OPENAI_API_KEY")
        if env_api_key:
            self.client = OpenAI(api_key=env_api_key)
            logger.debug("OpenAI client initialized with API key from environment variable")
            return
        
        # If we get here, we couldn't initialize the client
        raise ConfigurationError(
            "Could not initialize OpenAI client. Please provide an API key directly, "
            "through a config file, or set the OPENAI_API_KEY environment variable."
        )
    
    def _log_interaction(
        self,
        email: Dict[str, str],
        prompt: str,
        response: str,
        category_result: str
    ) -> None:
        """Log OpenAI API interaction for debugging.
        
        Args:
            email: The email that was categorized
            prompt: The prompt sent to OpenAI
            response: The response from OpenAI
            category_result: The final category assigned
        """
        try:
            # Extract sender name from email address
            from_addr = email.get('from', '')
            sender_name = from_addr.split('<')[0].strip() if '<' in from_addr else from_addr
            
            # Log a concise summary to the application log
            logger.info(
                f"Categorized: {sender_name} | "
                f"Subject: {email.get('subject', '')[:40]}... | "
                f"Category: {category_result}"
            )
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
    
    def _prepare_category_info(self, categories: List[Category]) -> List[Dict[str, str]]:
        """Extract category information.
        
        Args:
            categories: List of Category objects
            
        Returns:
            List of dictionaries with category information
        """
        category_info = []
        for category in categories:
            category_info.append({
                "name": category.name,
                "description": category.description,
                "folder": getattr(category, "folder_name", category.name)
            })
        return category_info
    
    def _create_system_prompt(self, categories: List[Category]) -> str:
        """Create the system prompt for the OpenAI API.
        
        Args:
            categories: List of Category objects
            
        Returns:
            System prompt string
        """
        category_info = self._prepare_category_info(categories)
        category_names = [c.name for c in categories]
        
        return f"""You are an email categorization assistant. Your task is to categorize emails into one of the following categories:

{json.dumps(category_info, indent=2)}

For each email, respond with a JSON object containing:
1. "category": The category name (must be one of: {', '.join(category_names)})
2. "confidence": Your confidence level (0-100)
3. "reasoning": Brief explanation of your categorization

Analyze the email's subject, sender, and content to determine the most appropriate category.
Use the category descriptions to guide your decision.
"""
    
    def _create_user_prompt(self, emails: List[Dict[str, str]], batch_size: int) -> str:
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
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call the OpenAI API with the given prompts.
        
        Args:
            system_prompt: The system prompt
            user_prompt: The user prompt
            
        Returns:
            The response text from OpenAI
            
        Raises:
            APIError: If there's an error calling the API
        """
        if not self.client:
            raise APIError("OpenAI client not initialized")
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                frequency_penalty=self.config.frequency_penalty,
                presence_penalty=self.config.presence_penalty
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise APIError(f"Error calling OpenAI API: {e}")
    
    def _extract_json_objects(self, response_text: str) -> List[str]:
        """Extract JSON objects from a text response.
        
        Args:
            response_text: The text containing JSON objects
            
        Returns:
            List of JSON object strings
        """
        return re.findall(r'\{[^{}]*\}', response_text)
    
    def _parse_json_object(self, json_str: str) -> Dict[str, Any]:
        """Parse a JSON object string.
        
        Args:
            json_str: The JSON object string
            
        Returns:
            Parsed JSON object as a dictionary
            
        Raises:
            json.JSONDecodeError: If the JSON is invalid
        """
        return json.loads(json_str)
    
    def _validate_category(
        self,
        result: Dict[str, Any],
        valid_categories: List[str],
        categories: List[Category]
    ) -> Dict[str, Any]:
        """Validate and normalize a category in a result.
        
        Args:
            result: The result dictionary
            valid_categories: List of valid category names (uppercase)
            categories: List of Category objects
            
        Returns:
            The validated and normalized result dictionary
        """
        # Ensure category is valid
        if "category" in result:
            category = result["category"].upper()
            if category in valid_categories:
                result["category"] = next((cat for cat in categories if cat.name == category), None)
            else:
                # Default to INBOX if category is invalid
                logger.warning(f"Invalid category: {category}, defaulting to INBOX")
                result["category"] = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
                result["confidence"] = 0
                result["reasoning"] = f"Invalid category: {category}, defaulting to INBOX"
        else:
            result["category"] = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
            result["confidence"] = 0
            result["reasoning"] = "Missing category in response, defaulting to INBOX"
        
        return result
    
    def _parse_response(
        self,
        response_text: str,
        categories: List[Category],
        batch_size: int
    ) -> List[Dict[str, Any]]:
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
            json_objects = self._extract_json_objects(response_text)
            
            # Get valid category names (uppercase for case-insensitive comparison)
            valid_categories = [c.name.upper() for c in categories]
            
            for json_obj in json_objects:
                try:
                    result = self._parse_json_object(json_obj)
                    result = self._validate_category(result, valid_categories, categories)
                    results.append(result)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON object: {json_obj}")
                    inbox_category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
                    results.append({
                        "category": inbox_category,
                        "confidence": 0,
                        "reasoning": "Failed to parse response"
                    })
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            # Fallback: create default results
            inbox_category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
            results = [{
                "category": inbox_category,
                "confidence": 0,
                "reasoning": "Failed to parse response"
            }] * batch_size
        
        # Ensure we have a result for each email
        while len(results) < batch_size:
            inbox_category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
            results.append({
                "category": inbox_category,
                "confidence": 0,
                "reasoning": "Missing from response"
            })
        
        return results
    
    def categorize_emails(
        self,
        emails: List[Dict[str, str]],
        categories: List[Category]
    ) -> List[Dict[str, Any]]:
        """Categorize a batch of emails.
        
        Args:
            emails: List of email dictionaries
            categories: List of Category objects
            
        Returns:
            List of dictionaries with categorization results
        """
        if not emails:
            return []
        
        # Limit batch size to the number of emails
        batch_size = min(self.config.batch_size, len(emails))
        
        try:
            # Create prompts
            system_prompt = self._create_system_prompt(categories)
            user_prompt = self._create_user_prompt(emails, batch_size)
            
            # Call OpenAI API
            response_text = self._call_api(system_prompt, user_prompt)
            
            # Parse response
            results = self._parse_response(response_text, categories, batch_size)
            
            # Log interaction for debugging with actual categories
            for i, email in enumerate(emails[:batch_size]):
                if i < len(results):
                    category_result = results[i]["category"]
                    self._log_interaction(
                        email, 
                        f"Batch categorization with {self.config.model} (email {i+1} of {batch_size})", 
                        response_text, 
                        category_result
                    )
            
            return results
        except APIError as e:
            logger.error(f"API error during categorization: {e}")
            # Fallback: categorize all as inbox
            inbox_category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
            fallback_results = [{
                "category": inbox_category,
                "confidence": 0,
                "reasoning": f"API error: {str(e)}"
            }] * batch_size
            
            # Log the fallback categorization
            for i, email in enumerate(emails[:batch_size]):
                self._log_interaction(
                    email,
                    f"Batch categorization with {self.config.model} failed (email {i+1} of {batch_size})",
                    f"Error: {str(e)}",
                    "INBOX"
                )
            
            return fallback_results
        except Exception as e:
            logger.error(f"Unexpected error during categorization: {e}")
            # Return default categories for all emails
            inbox_category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
            return [{
                "category": inbox_category,
                "confidence": 0,
                "reasoning": f"Error during categorization: {str(e)}"
            } for _ in range(len(emails))]


# For backward compatibility with existing code
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


# Backward compatibility functions
def initialize_openai_client(api_key=None, config_path=None):
    """Initialize the OpenAI client (backward compatibility).
    
    This function creates a global categorizer instance for backward compatibility.
    New code should use the EmailCategorizer class directly.
    """
    global _global_categorizer
    _global_categorizer = EmailCategorizer(api_key=api_key, config_path=config_path)
    return _global_categorizer


def batch_categorize_emails_for_account(emails, account, batch_size=10, model="gpt-4o-mini"):
    """Categorize a batch of emails for an account.
    
    Args:
        emails: List of Email objects
        account: The email account with category definitions
        batch_size: Maximum number of emails to process in one batch
        model: The OpenAI model to use
        
    Returns:
        List of dictionaries with category information
    """
    try:
        # Convert Email objects to dictionaries and check for pre-defined categories
        email_dicts = []
        results = []
        for email in emails:
            if isinstance(email, dict):
                email_dicts.append(email)
                results.append(None)  # Placeholder for later categorization
            else:
                email_dict = {
                    'from': email.from_addr,
                    'to': email.to_addr,
                    'subject': email.subject,
                    'date': email.date,
                    'body': email.body
                }
                email_dicts.append(email_dict)
                results.append(None)  # Placeholder for later categorization
        
        # Create categorizer config
        config = CategorizerConfig(model=model, batch_size=batch_size)
        
        # Create categorizer instance
        categorizer = EmailCategorizer(config=config)
        
        # Get categories from account
        categories = [Category(c.name, c.description, c.foldername) for c in account.categories]
        
        # Only categorize emails that don't have pre-defined categories
        uncategorized_emails = [email for i, email in enumerate(email_dicts) if results[i] is None]
        if uncategorized_emails:
            api_results = categorizer.categorize_emails(uncategorized_emails, categories)
            
            # Merge results
            j = 0
            for i in range(len(results)):
                if results[i] is None:
                    results[i] = api_results[j]
                    j += 1
        
        return results
    except Exception as e:
        logger.error(f"Unexpected error during categorization: {e}")
        # Return default categories for all emails
        inbox_category = next((cat for cat in account.categories if cat.name == "INBOX"), account.categories[0])
        return [{
            "category": Category(inbox_category.name, inbox_category.description, inbox_category.foldername),
            "confidence": 0,
            "reasoning": f"Error during categorization: {str(e)}"
        } for _ in range(len(emails))]


# Initialize global categorizer for backward compatibility
_global_categorizer = None 