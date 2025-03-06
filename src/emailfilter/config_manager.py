"""Manages configuration loading and validation."""

import yaml
import logging
from typing import Dict, List, Optional

from .models import EmailAccount, ProcessingOptions
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
                account = EmailAccount(
                    name=account_config.get("name", ""),
                    email_address=account_config.get("email", ""),
                    password=account_config.get("password", ""),
                    imap_server=account_config.get("imap_server", ""),
                    imap_port=account_config.get("imap_port", 993),
                    ssl=account_config.get("ssl", True),
                    folders=account_config.get("folders", ["INBOX"]),
                )
                self.accounts.append(account)
            
            # Load options
            options_config = config.get("options", {})
            
            # Get custom categories if defined
            custom_categories = options_config.get("custom_categories")
            
            # Get category folders mapping
            category_folders = options_config.get("category_folders")
            
            self.options = ProcessingOptions(
                max_emails_per_run=options_config.get("max_emails_per_run", 100),
                batch_size=options_config.get("batch_size", 10),
                idle_timeout=options_config.get("idle_timeout", 1740),
                move_emails=options_config.get("move_emails", True),
                category_folders=category_folders,
                custom_categories=custom_categories
            )
            
            # Update the EmailCategory enum with custom categories if provided
            if custom_categories:
                # Recreate the EmailCategory enum with custom categories
                categorizer.EmailCategory = categorizer.create_email_category_enum(custom_categories)
                logger.info(f"Using custom categories: {custom_categories}")
            
            # Load OpenAI API key
            self.openai_api_key = config.get("openai_api_key")
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not found in config file")
            
            logger.info(f"Loaded configuration with {len(self.accounts)} accounts")
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise ValueError(f"Config file not found: {self.config_path}")
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
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not configured") 