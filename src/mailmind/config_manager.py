"""Manages configuration loading and validation."""

import yaml
import logging
from typing import Dict, List, Optional
from pathlib import Path

from .models import (
    Config, EmailAccount, ProcessingOptions, Category,
    EmailAccountConfig, OpenAIConfig, ProcessingConfig, LoggingConfig
)
from .config_validator import ConfigValidator
from .config_converter import ConfigConverter

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
        """Load configuration from YAML file."""
        try:
            # Load YAML config
            with open(self.config_path, "r") as f:
                yaml_config = yaml.safe_load(f)
            
            # Validate and convert to Pydantic model
            self.config = Config(**yaml_config)
            ConfigValidator.validate(self.config)
            
            logger.debug("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def validate(self) -> None:
        """Validate the loaded configuration."""
        ConfigValidator.validate(self.config)
    
    @property
    def accounts(self) -> List[EmailAccount]:
        """Get list of email accounts."""
        if not self.config:
            return []
        return [ConfigConverter.to_email_account(acc) for acc in self.config.accounts]
    
    @property
    def options(self) -> ProcessingOptions:
        """Get processing options."""
        if not self.config:
            return ProcessingOptions()
        return ConfigConverter.to_processing_options(self.config.processing, self.config.openai)
    
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