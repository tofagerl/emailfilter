"""Configuration manager for email processing."""

import os
import logging
from typing import Dict, List, Optional
import yaml

from .inference.models import Account, ProcessingOptions, Category
from .inference import categorizer

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: str):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.accounts: List[Account] = []
        self.options: ProcessingOptions = ProcessingOptions()
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load and validate configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            
            # Load accounts
            for account_config in config.get("accounts", []):
                # Load categories for this account
                categories = []
                for category_config in account_config.get("categories", []):
                    category = Category(
                        name=category_config.get("name", ""),
                        description=category_config.get("description", ""),
                        foldername=category_config.get("foldername", "")
                    )
                    categories.append(category)
                
                account = Account(
                    name=account_config.get("name", ""),
                    email_address=account_config.get("email", ""),
                    password=account_config.get("password", ""),
                    imap_server=account_config.get("imap_server", ""),
                    imap_port=account_config.get("imap_port", 993),
                    ssl=account_config.get("ssl", True),
                    folders=account_config.get("folders", None),
                    categories=categories
                )
                self.accounts.append(account)
            
            # Load processing options
            options_config = config.get("options", {})
            self.options = ProcessingOptions(
                max_emails_per_run=options_config.get("max_emails_per_run", 100),
                batch_size=options_config.get("batch_size", 10),
                idle_timeout=options_config.get("idle_timeout", 1740),
                move_emails=options_config.get("move_emails", True)
            )
            
            logger.info(f"Loaded configuration from {self.config_path}")
            logger.debug(f"Found {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def validate(self) -> None:
        """Validate the loaded configuration."""
        if not self.accounts:
            raise ValueError("No email accounts configured")
        
        for account in self.accounts:
            if not account.name or not account.email_address or not account.password or not account.imap_server:
                raise ValueError(f"Invalid account configuration for {account}")
            
            # Validate categories
            category_names = set()
            for category in account.categories:
                if not category.name:
                    raise ValueError(f"Category name cannot be empty for account {account.name}")
                if category.name.upper() in category_names:
                    raise ValueError(f"Duplicate category name '{category.name}' for account {account.name}")
                category_names.add(category.name.upper()) 