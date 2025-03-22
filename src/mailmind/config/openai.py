"""OpenAI configuration management."""

from typing import Optional
from ..models import OpenAIConfig

class OpenAIConfigManager:
    """Manages OpenAI configuration."""
    
    def __init__(self, config: Optional[OpenAIConfig] = None):
        """Initialize OpenAI config manager.
        
        Args:
            config: OpenAI configuration
        """
        self.config = config
    
    @property
    def api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self.config.api_key if self.config else None
    
    @property
    def model(self) -> str:
        """Get OpenAI model name."""
        return self.config.model if self.config else "gpt-4o-mini"
    
    @property
    def temperature(self) -> float:
        """Get OpenAI temperature setting."""
        return self.config.temperature if self.config else 0.7
    
    @property
    def max_tokens(self) -> int:
        """Get OpenAI max tokens setting."""
        return self.config.max_tokens if self.config else 1000
    
    @property
    def batch_size(self) -> int:
        """Get OpenAI batch size setting."""
        return self.config.batch_size if self.config else 10 