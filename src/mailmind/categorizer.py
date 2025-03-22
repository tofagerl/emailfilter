"""Email categorization using OpenAI API."""

import os
import logging
import yaml
import json
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field

import openai
from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice, ChatCompletionMessage

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Default categories if not specified in config
DEFAULT_CATEGORIES = ["SPAM", "RECEIPTS", "PROMOTIONS", "UPDATES", "INBOX"]


class EmailCategory(Enum):
    """Enum for email categories."""
    SPAM = auto()
    RECEIPTS = auto()
    PROMOTIONS = auto()
    UPDATES = auto()
    INBOX = auto()
    
    def __str__(self) -> str:
        return self.name.capitalize()


@dataclass
class Category:
    """Represents an email category with its properties."""
    name: str
    description: str
    foldername: str
    
    def __post_init__(self):
        """Ensure name is uppercase after initialization."""
        self.name = self.name.upper()
    
    def __str__(self) -> str:
        return self.name


@dataclass
class EmailAccount:
    """Represents an email account configuration."""
    name: str
    email: str
    password: str
    imap_server: str
    imap_port: int = 993
    ssl: bool = True
    folders: List[str] = field(default_factory=list)
    categories: List[Category] = field(default_factory=list)
    
    def __post_init__(self):
        if self.folders is None:
            self.folders = ["INBOX"]
        
        # Set default categories if none provided
        if self.categories is None:
            self.categories = [
                Category("SPAM", "Unwanted or malicious emails", "[Spam]"),
                Category("RECEIPTS", "Purchase confirmations and receipts", "[Receipts]"),
                Category("PROMOTIONS", "Marketing and promotional emails", "[Promotions]"),
                Category("UPDATES", "Updates and notifications", "[Updates]"),
                Category("INBOX", "Important emails that need attention", "INBOX")
            ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.email})"
    
    def get_category_names(self) -> List[str]:
        """Get list of category names for this account."""
        return [category.name for category in self.categories]
    
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """Get a category by its name."""
        name_upper = name.upper()
        for category in self.categories:
            if category.name.upper() == name_upper:
                return category
        return None
    
    def get_folder_for_category(self, category_name: str) -> str:
        """Get the folder name for a given category."""
        category = self.get_category_by_name(category_name)
        if category:
            return category.foldername
        return "INBOX"  # Default to INBOX if category not found


class CategorizationError(Exception):
    """Base exception for categorization errors."""
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


class EmailCategorizer:
    """Email categorization using OpenAI API."""

    _global_categorizer = None

    class APIError(Exception):
        """Error when calling the OpenAI API."""
        pass

    def __init__(self, model: str = "gpt-4", categories: List[Category] = None, api_key: str = None, config_path: str = None, config_manager = None):
        """Initialize the categorizer.
        
        Args:
            model: The OpenAI model to use
            categories: List of categories to use for categorization
            api_key: Optional OpenAI API key
            config_path: Optional path to config file
            config_manager: Optional ConfigManager instance
        """
        self.model = model
        if config_manager:
            self.categories = config_manager.accounts[0].categories if config_manager.accounts else []
        else:
            self.categories = categories or []
        self.client = None
        self.api_key = api_key
        self.config_path = config_path
        self.system_prompt = self._create_system_prompt(self.categories)
        self._initialize_openai_client()

    def _initialize_openai_client(self) -> None:
        """Initialize the OpenAI client."""
        if self.api_key:
            logger.debug("OpenAI client initialized with provided API key")
            self.client = OpenAI(api_key=self.api_key)
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                logger.debug("OpenAI client initialized with API key from environment variable")
                self.client = OpenAI(api_key=api_key)
            else:
                logger.debug("OpenAI client initialized with default configuration")
                self.client = OpenAI()

    def _create_system_prompt(self, categories: List[Category]) -> str:
        """Create the system prompt for the OpenAI API.
        
        Args:
            categories: List of Category objects
            
        Returns:
            System prompt string
        """
        category_info = self._prepare_category_info(categories)
        category_lines = [
            f"{cat['name']}: {cat['description']} (folder: {cat['folder']})"
            for cat in category_info
        ]
        
        return (
            "You are an email categorization assistant. Your task is to categorize "
            "emails into one of the following categories:\n\n"
            f"{'\n'.join(category_lines)}\n\n"
            "For each email, return a JSON object with the following fields:\n"
            "- category: The category name (must be one of the above)\n"
            "- confidence: A number between 0 and 100 indicating confidence\n"
            "- reasoning: A brief explanation of why this category was chosen\n\n"
            "Return one JSON object per line for batch processing."
        )

    def _prepare_category_info(self, categories: List[Category]) -> List[Dict[str, str]]:
        """Prepare category information for the system prompt.
        
        Args:
            categories: List of Category objects
            
        Returns:
            List of dictionaries containing category information
        """
        if not categories:
            categories = [
                Category("INBOX", "Default inbox", "INBOX")
            ]
        
        return [
            {
                "name": category.name,
                "description": category.description,
                "folder": category.foldername
            }
            for category in categories
        ]

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
    
    def _create_user_prompt(self, emails: List[Dict[str, str]], batch_size: int) -> str:
        """Create the user prompt for the OpenAI API.
        
        Args:
            emails: List of email dictionaries
            batch_size: Number of emails to process
            
        Returns:
            Formatted prompt string
        """
        # Format each email for the prompt
        email_prompts = []
        for i, email in enumerate(emails[:batch_size]):
            email_prompt = (
                f"Email {i+1}:\n"
                f"From: {email.get('from', '')}\n"
                f"To: {email.get('to', '')}\n"
                f"Subject: {email.get('subject', '')}\n"
                f"Body: {email.get('body', '')}\n"
            )
            email_prompts.append(email_prompt)

        # Combine all email prompts
        return "Categorize the following emails. Respond with one JSON object per line:\n\n" + "\n".join(email_prompts)
    
    def _call_api(self, prompt: str) -> str:
        """Call the OpenAI API with the given prompt.
        
        Args:
            prompt: The user prompt
            
        Returns:
            API response text
            
        Raises:
            APIError: If the API call fails
        """
        if not self.client:
            raise self.APIError("OpenAI client not initialized")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Handle different response formats
            if hasattr(response, 'choices') and response.choices:
                if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                    return response.choices[0].message.content
                elif hasattr(response.choices[0], 'text'):
                    return response.choices[0].text
            elif hasattr(response, 'content'):
                return response.content
            
            # If we get here, try to convert the response to a string
            return str(response)
        except Exception as e:
            raise self.APIError(f"API error: {str(e)}")
    
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
    
    def categorize_emails(self, emails: List[Dict[str, str]], categories: List[Category] = None) -> List[Dict[str, Any]]:
        """Categorize a batch of emails.
        
        Args:
            emails: List of email dictionaries with 'from', 'to', 'subject', and 'body' fields
            categories: Optional list of categories to use (defaults to self.categories)
            
        Returns:
            List of dictionaries with category, confidence, and reasoning
        """
        if not self.client:
            raise self.APIError("OpenAI client not initialized")

        # Use provided categories or fall back to instance categories
        categories = categories or self.categories
        if not categories:
            categories = [Category("INBOX", "Default inbox", "INBOX")]

        # Create user prompt
        user_prompt = self._create_user_prompt(emails, len(emails))

        try:
            # Call OpenAI API
            response_text = self._call_api(user_prompt)

            # Parse response
            json_objects = self._extract_json_objects(response_text)
            if not json_objects:
                # Return default results for all emails
                inbox_category = next((c for c in categories if c.name == "INBOX"), categories[0])
                return [{
                    "category": inbox_category,
                    "confidence": 0,
                    "reasoning": "Failed to parse response"
                }] * len(emails)

            # Process results
            results = []
            for i, email in enumerate(emails):
                try:
                    if i >= len(json_objects):
                        # Not enough results
                        inbox_category = next((c for c in categories if c.name == "INBOX"), categories[0])
                        results.append({
                            "category": inbox_category,
                            "confidence": 0,
                            "reasoning": "No category result found"
                        })
                        continue

                    # Parse the result
                    result = json.loads(json_objects[i])
                    category_name = result.get("category", "INBOX").upper()
                    confidence = result.get("confidence", 0)
                    reasoning = result.get("reasoning", "No reasoning provided")

                    # Find matching category
                    category = next(
                        (c for c in categories if c.name == category_name),
                        None
                    )

                    if category is None:
                        # Invalid category, default to INBOX
                        category = next((c for c in categories if c.name == "INBOX"), categories[0])
                        confidence = 0
                        reasoning = f"Invalid category: {category_name}, defaulting to INBOX"

                    results.append({
                        "category": category,
                        "confidence": confidence,
                        "reasoning": reasoning
                    })

                    # Log the result
                    logger.info(
                        f"Categorized: {email.get('from', 'unknown')} | "
                        f"Subject: {email.get('subject', '')[:30]}... | "
                        f"Category: {category.name}"
                    )

                except Exception as e:
                    logger.error(f"Error processing result for email {i}: {e}")
                    inbox_category = next((c for c in categories if c.name == "INBOX"), categories[0])
                    results.append({
                        "category": inbox_category,
                        "confidence": 0,
                        "reasoning": f"Error processing result: {str(e)}"
                    })

            return results

        except self.APIError as e:
            logger.error(f"API error during categorization: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during categorization: {e}")
            raise self.APIError(f"Error during categorization: {e}")

    @classmethod
    def initialize_openai_client(cls, api_key: str = None, config_path: str = None) -> 'EmailCategorizer':
        """Initialize the OpenAI client.
        
        Args:
            api_key: Optional OpenAI API key
            config_path: Optional path to config file
            
        Returns:
            EmailCategorizer instance
        """
        if cls._global_categorizer is None:
            # If config_path is provided, try to load API key from config file
            if config_path and not api_key:
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        api_key = config.get('openai_api_key')
                except Exception as e:
                    logger.error(f"Failed to load config file: {e}")

            cls._global_categorizer = cls(api_key=api_key, config_path=config_path)
        return cls._global_categorizer

    @classmethod
    def batch_categorize_emails_for_account(cls, emails: List[Dict[str, str]], account: EmailAccount, batch_size: int = 5, model: str = "gpt-4") -> List[Dict[str, Any]]:
        """Categorize a batch of emails for an account.
        
        Args:
            emails: List of email dictionaries
            account: Email account with category configuration
            batch_size: Number of emails to process in each batch
            model: OpenAI model to use
            
        Returns:
            List of dictionaries with category, confidence, and reasoning
        """
        results = []
        categorizer = cls(model=model, categories=account.categories)

        # Process emails in batches
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            try:
                batch_results = categorizer.categorize_emails(batch, account.categories)
                results.extend(batch_results)
            except cls.APIError as e:
                # Handle API errors by defaulting to INBOX with error message
                for _ in batch:
                    results.append({
                        "category": next((c for c in account.categories if c.name == "INBOX"), account.categories[0]),
                        "confidence": 0,
                        "reasoning": f"API error: {str(e)}"
                    })
            except Exception as e:
                # Handle other errors by defaulting to INBOX with error message
                for _ in batch:
                    results.append({
                        "category": next((c for c in account.categories if c.name == "INBOX"), account.categories[0]),
                        "confidence": 0,
                        "reasoning": f"Error: {str(e)}"
                    })

        return results


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
    
    # If config_path is provided, try to load API key from config file
    if config_path:
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                api_key = config.get('openai_api_key')
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    _global_categorizer = EmailCategorizer(api_key=api_key)
    return _global_categorizer


def batch_categorize_emails_for_account(emails: List[Dict[str, str]], account: EmailAccount, batch_size: int = 5, model: str = "gpt-4") -> List[Dict[str, Any]]:
    """Categorize a batch of emails for an account.
    
    Args:
        emails: List of email dictionaries
        account: Email account with category configuration
        batch_size: Number of emails to process in each batch
        model: OpenAI model to use
        
    Returns:
        List of dictionaries with category, confidence, and reasoning
    """
    results = []
    categorizer = EmailCategorizer(model=model, categories=account.categories)

    # Process emails in batches
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        try:
            batch_results = categorizer.categorize_emails(batch, account.categories)
            results.extend(batch_results)
        except self.APIError as e:
            # Handle API errors by defaulting to INBOX with error message
            for _ in batch:
                results.append({
                    "category": next((c for c in account.categories if c.name == "INBOX"), account.categories[0]),
                    "confidence": 0,
                    "reasoning": f"API error: {str(e)}"
                })
        except Exception as e:
            # Handle other errors by defaulting to INBOX with error message
            for _ in batch:
                results.append({
                    "category": next((c for c in account.categories if c.name == "INBOX"), account.categories[0]),
                    "confidence": 0,
                    "reasoning": f"Error: {str(e)}"
                })

    return results


# Initialize global categorizer for backward compatibility
_global_categorizer = None 