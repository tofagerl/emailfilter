"""Validates configuration values."""

import logging
from typing import List
from ..models import Config, EmailAccountConfig

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validates configuration values."""
    
    @staticmethod
    def validate(config: Config) -> None:
        """Validate the configuration.
        
        Args:
            config: The configuration to validate
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not config:
            raise ValueError("Configuration not loaded")
        
        if not config.accounts:
            raise ValueError("No email accounts configured")
        
        ConfigValidator._validate_accounts(config.accounts)
    
    @staticmethod
    def _validate_accounts(accounts: List[EmailAccountConfig]) -> None:
        """Validate email accounts configuration.
        
        Args:
            accounts: List of email account configurations
            
        Raises:
            ValueError: If account configuration is invalid
        """
        for account in accounts:
            if not account.name or not account.email or not account.password or not account.imap_server:
                raise ValueError(f"Invalid account configuration for {account}")
            
            ConfigValidator._validate_categories(account)
    
    @staticmethod
    def _validate_categories(account: EmailAccountConfig) -> None:
        """Validate categories for an account.
        
        Args:
            account: The email account configuration
            
        Raises:
            ValueError: If category configuration is invalid
        """
        category_names = set()
        for category in account.categories:
            if not category.name:
                raise ValueError(f"Category name cannot be empty for account {account.name}")
            if category.name.upper() in category_names:
                raise ValueError(f"Duplicate category name '{category.name}' for account {account.name}")
            category_names.add(category.name.upper()) 