"""Manages configuration loading and validation."""

import yaml
import logging
import os
from typing import Dict, List, Optional
from pathlib import Path

from .models import (
    Config, EmailAccount, ProcessingOptions, Category,
    EmailAccountConfig, OpenAIConfig, ProcessingConfig, LoggingConfig
)

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: str):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config: Optional[Config] = None
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file and environment variables."""
        try:
            # Load YAML config
            with open(self.config_path, "r") as f:
                yaml_config = yaml.safe_load(f)
            
            # Override with environment variables
            env_config = self._load_env_config()
            merged_config = self._merge_configs(yaml_config, env_config)
            
            # Validate and convert to Pydantic model
            self.config = Config(**merged_config)
            
            logger.debug("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def _load_env_config(self) -> Dict:
        """Load configuration from environment variables.
        
        Returns:
            Dictionary of environment-based configuration
        """
        env_config = {
            "openai": {
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "model": os.environ.get("MAILMIND_OPENAI_MODEL"),
                "temperature": os.environ.get("MAILMIND_OPENAI_TEMPERATURE"),
                "max_tokens": os.environ.get("MAILMIND_OPENAI_MAX_TOKENS"),
                "batch_size": os.environ.get("MAILMIND_OPENAI_BATCH_SIZE")
            },
            "processing": {
                "move_emails": os.environ.get("MAILMIND_MOVE_EMAILS"),
                "max_emails_per_run": os.environ.get("MAILMIND_MAX_EMAILS"),
                "lookback_days": os.environ.get("MAILMIND_LOOKBACK_DAYS"),
                "min_samples_per_category": os.environ.get("MAILMIND_MIN_SAMPLES"),
                "test_size": os.environ.get("MAILMIND_TEST_SIZE"),
                "idle_timeout": os.environ.get("MAILMIND_IDLE_TIMEOUT"),
                "reconnect_delay": os.environ.get("MAILMIND_RECONNECT_DELAY")
            },
            "logging": {
                "level": os.environ.get("MAILMIND_LOG_LEVEL"),
                "file": os.environ.get("MAILMIND_LOG_FILE"),
                "format": os.environ.get("MAILMIND_LOG_FORMAT")
            }
        }
        
        # Remove None values
        return self._clean_dict(env_config)
    
    def _merge_configs(self, yaml_config: Dict, env_config: Dict) -> Dict:
        """Merge YAML and environment configurations.
        
        Args:
            yaml_config: Configuration from YAML file
            env_config: Configuration from environment variables
            
        Returns:
            Merged configuration dictionary
        """
        merged = yaml_config.copy()
        
        # Deep merge environment config
        for section, values in env_config.items():
            if section not in merged:
                merged[section] = {}
            if isinstance(values, dict):
                merged[section].update(values)
            else:
                merged[section] = values
        
        return merged
    
    def _clean_dict(self, d: Dict) -> Dict:
        """Remove None values from dictionary.
        
        Args:
            d: Dictionary to clean
            
        Returns:
            Cleaned dictionary
        """
        if not isinstance(d, dict):
            return d
        return {k: self._clean_dict(v) for k, v in d.items() if v is not None}
    
    def validate(self) -> None:
        """Validate the loaded configuration."""
        if not self.config:
            raise ValueError("Configuration not loaded")
        
        if not self.config.accounts:
            raise ValueError("No email accounts configured")
        
        # Validate accounts
        for account in self.config.accounts:
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
    
    @property
    def accounts(self) -> List[EmailAccount]:
        """Get list of email accounts."""
        if not self.config:
            return []
        return [
            EmailAccount(
                name=acc.name,
                email=acc.email,
                password=acc.password,
                imap_server=acc.imap_server,
                imap_port=acc.imap_port,
                ssl=acc.ssl,
                folders=acc.folders,
                categories=[
                    Category(
                        name=cat.name,
                        description=cat.description,
                        foldername=cat.foldername
                    ) for cat in acc.categories
                ]
            ) for acc in self.config.accounts
        ]
    
    @property
    def options(self) -> ProcessingOptions:
        """Get processing options."""
        if not self.config:
            return ProcessingOptions()
        return ProcessingOptions(
            max_emails_per_run=self.config.processing.max_emails_per_run,
            batch_size=self.config.openai.batch_size,
            idle_timeout=self.config.processing.idle_timeout,
            move_emails=self.config.processing.move_emails,
            model=self.config.openai.model
        )
    
    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self.config.openai.api_key if self.config else None
    
    @property
    def openai_model(self) -> str:
        """Get OpenAI model name."""
        return self.config.openai.model if self.config else "gpt-4o-mini"
    
    @property
    def openai_temperature(self) -> float:
        """Get OpenAI temperature setting."""
        return self.config.openai.temperature if self.config else 0.7
    
    @property
    def openai_max_tokens(self) -> int:
        """Get OpenAI max tokens setting."""
        return self.config.openai.max_tokens if self.config else 1000 