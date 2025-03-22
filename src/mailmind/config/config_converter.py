"""Converts between different config formats."""

from typing import List
from ..models import (
    EmailAccount, Category, EmailAccountConfig, CategoryConfig,
    ProcessingOptions, ProcessingConfig, OpenAIConfig
)

class ConfigConverter:
    """Converts between different config formats."""
    
    @staticmethod
    def to_email_account(acc: EmailAccountConfig) -> EmailAccount:
        """Convert EmailAccountConfig to EmailAccount.
        
        Args:
            acc: The email account configuration
            
        Returns:
            The converted EmailAccount
        """
        return EmailAccount(
            name=acc.name,
            email=acc.email,
            password=acc.password,
            imap_server=acc.imap_server,
            imap_port=acc.imap_port,
            ssl=acc.ssl,
            folders=acc.folders,
            categories=[ConfigConverter.to_category(cat) for cat in acc.categories]
        )
    
    @staticmethod
    def to_category(cat: CategoryConfig) -> Category:
        """Convert CategoryConfig to Category.
        
        Args:
            cat: The category configuration
            
        Returns:
            The converted Category
        """
        return Category(
            name=cat.name,
            description=cat.description,
            foldername=cat.foldername
        )
    
    @staticmethod
    def to_processing_options(processing: ProcessingConfig, openai: OpenAIConfig) -> ProcessingOptions:
        """Convert ProcessingConfig and OpenAIConfig to ProcessingOptions.
        
        Args:
            processing: The processing configuration
            openai: The OpenAI configuration
            
        Returns:
            The converted ProcessingOptions
        """
        return ProcessingOptions(
            max_emails_per_run=processing.max_emails_per_run,
            batch_size=openai.batch_size,
            idle_timeout=processing.idle_timeout,
            move_emails=processing.move_emails,
            model=openai.model
        ) 