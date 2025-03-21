"""Manages configuration loading and validation."""

import yaml
import logging
import os
from typing import Dict, List, Optional

from .models import EmailAccount, ProcessingOptions, Category
from . import categorizer

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: str):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.accounts: List[EmailAccount] = []
        self.options: ProcessingOptions = ProcessingOptions()
        self.openai_api_key: Optional[str] = None
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            
            # Load accounts
            for account_config in config.get("accounts", []):
                # Load account-specific categories if defined
                categories = None
                if "categories" in account_config:
                    categories = []
                    for cat_config in account_config.get("categories", []):
                        category = Category(
                            name=cat_config.get("name", "").upper(),
                            description=cat_config.get("description", ""),
                            foldername=cat_config.get("folder", "INBOX")
                        )
                        categories.append(category)
                
                account = EmailAccount(
                    name=account_config.get("name", ""),
                    email=account_config.get("email", ""),
                    password=account_config.get("password", ""),
                    imap_server=account_config.get("imap_server", ""),
                    imap_port=account_config.get("imap_port", 993),
                    ssl=account_config.get("ssl", True),
                    folders=account_config.get("folders", ["INBOX"]),
                    categories=categories
                )
                self.accounts.append(account)
            
            # Load OpenAI API key
            self.openai_api_key = config.get("openai_api_key")
            if not self.openai_api_key:
                # Try environment variable
                self.openai_api_key = os.environ.get("OPENAI_API_KEY")
                if not self.openai_api_key:
                    raise ValueError("OpenAI API key not found in config or environment")
            
            # Load OpenAI settings
            openai_config = config.get("openai", {})
            self.openai_model = openai_config.get("model", "gpt-4")
            self.openai_temperature = openai_config.get("temperature", 0.7)
            self.openai_max_tokens = openai_config.get("max_tokens", 1000)
            
            # Load processing options
            processing_config = config.get("processing", {})
            self.batch_size = processing_config.get("batch_size", 10)
            self.lookback_days = processing_config.get("lookback_days", 30)
            self.min_samples_per_category = processing_config.get("min_samples_per_category", 5)
            self.test_size = processing_config.get("test_size", 0.2)
            
            logger.debug("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def validate(self) -> None:
        """Validate the loaded configuration."""
        if not self.accounts:
            raise ValueError("No email accounts configured")
        
        for account in self.accounts:
            if not account.name or not account.email or not account.password or not account.imap_server:
                raise ValueError(f"Invalid account configuration for {account}")
            
            # Validate categories
            category_names = set()
            for category in account.categories:
                if not category.name:
                    raise ValueError(f"Category name cannot be empty for account {account.name}")
                if category.name.upper() in category_names:
                    raise ValueError(f"Duplicate category name '{category.name}' for account {account.name}")
                category_names.add(category.name.upper())
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not configured") 