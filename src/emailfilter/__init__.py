"""Email filtering and categorization package."""

from .inference.models import Account, Category, ProcessingOptions
from .inference.categorizer import initialize_openai_client, batch_categorize_emails_for_account

__version__ = "0.1.0"

__all__ = [
    "Account",
    "Category",
    "ProcessingOptions",
    "initialize_openai_client",
    "batch_categorize_emails_for_account",
] 