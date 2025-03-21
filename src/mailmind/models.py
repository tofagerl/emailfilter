"""Data models for email processing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from email.message import Message
from pydantic import BaseModel, Field, EmailStr, validator, field_validator

@dataclass
class Category:
    """Represents an email category with its properties."""
    name: str
    description: str
    foldername: str
    
    def __str__(self) -> str:
        return self.name

@dataclass
class Email:
    """Represents an email message with its metadata and content."""
    subject: str
    from_addr: str
    to_addr: str
    date: str
    body: str
    raw_message: bytes
    message_id: Optional[str] = None
    folder: Optional[str] = None
    attachments: Optional[List[bytes]] = field(default_factory=list)
    
    @classmethod
    def from_message(cls, message: Message, msg_id: Optional[int] = None) -> 'Email':
        """Create an Email instance from an email.message.Message."""
        attachments = []
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() != "text/plain" and part.get("Content-Disposition", "").startswith("attachment"):
                    attachments.append(part.get_payload(decode=True))
        
        return cls(
            subject=message.get("Subject", ""),
            from_addr=message.get("From", ""),
            to_addr=message.get("To", ""),
            date=message.get("Date", ""),
            body=cls._extract_body(message),
            raw_message=message.as_bytes(),
            message_id=message.get("Message-ID", ""),
            attachments=attachments
        )
    
    @staticmethod
    def _extract_body(message: Message) -> str:
        """Extract the body from an email message."""
        if message.is_multipart():
            text_parts = []
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    continue
                
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            text_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        continue
            
            return "\n".join(text_parts)
        else:
            try:
                charset = message.get_content_charset() or "utf-8"
                payload = message.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
                return ""
            except Exception:
                return ""

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

@dataclass
class ProcessingOptions:
    """Configuration options for email processing."""
    max_emails_per_run: int = 100
    batch_size: int = 10
    idle_timeout: int = 1740  # 29 minutes
    move_emails: bool = True
    model: str = "gpt-4o-mini"  # Default to GPT-4o mini
    
    def __post_init__(self):
        pass

class CategoryConfig(BaseModel):
    """Configuration for an email category."""
    name: str = Field(..., description="Name of the category")
    description: str = Field(default="", description="Description of the category")
    foldername: str = Field(..., description="IMAP folder name for this category")
    
    @field_validator('name')
    @classmethod
    def name_uppercase(cls, v: str) -> str:
        return v.upper()

class EmailAccountConfig(BaseModel):
    """Configuration for an email account."""
    name: str = Field(..., description="Name of the account")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Email password or app password")
    imap_server: str = Field(..., description="IMAP server address")
    imap_port: int = Field(default=993, description="IMAP server port")
    ssl: bool = Field(default=True, description="Use SSL for IMAP connection")
    folders: List[str] = Field(default_factory=lambda: ["INBOX"], description="List of folders to monitor")
    categories: List[CategoryConfig] = Field(default_factory=list, description="List of categories for this account")

class OpenAIConfig(BaseModel):
    """Configuration for OpenAI API."""
    api_key: str = Field(..., description="OpenAI API key")
    model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Model temperature")
    max_tokens: int = Field(default=1000, gt=0, description="Maximum tokens to generate")
    batch_size: int = Field(default=10, gt=0, description="Batch size for API calls")

class ProcessingConfig(BaseModel):
    """Configuration for email processing."""
    move_emails: bool = Field(default=True, description="Whether to move emails after categorization")
    max_emails_per_run: int = Field(default=100, gt=0, description="Maximum emails to process per run")
    lookback_days: int = Field(default=30, gt=0, description="Days to look back for processing")
    min_samples_per_category: int = Field(default=5, ge=0, description="Minimum samples per category for training")
    test_size: float = Field(default=0.2, ge=0.0, le=1.0, description="Test set size for training")
    idle_timeout: int = Field(default=1740, gt=0, description="IMAP IDLE timeout in seconds")
    reconnect_delay: int = Field(default=5, gt=0, description="Delay before reconnecting after error")

class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: str = Field(default="INFO", description="Logging level")
    file: Optional[str] = Field(default=None, description="Log file path")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")

class Config(BaseModel):
    """Main configuration model."""
    version: str = Field(default="1.0", description="Configuration version")
    openai: OpenAIConfig
    accounts: List[EmailAccountConfig]
    processing: ProcessingConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig) 