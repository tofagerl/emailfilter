"""Data models for email processing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from email.message import Message

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
    msg_id: Optional[int] = None
    folder: Optional[str] = None
    
    @classmethod
    def from_message(cls, message: Message, msg_id: Optional[int] = None) -> 'Email':
        """Create an Email instance from an email.message.Message."""
        return cls(
            subject=message.get("Subject", ""),
            from_addr=message.get("From", ""),
            to_addr=message.get("To", ""),
            date=message.get("Date", ""),
            body=cls._extract_body(message),
            raw_message=message.as_bytes(),
            msg_id=msg_id
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
    email_address: str
    password: str
    imap_server: str
    imap_port: int = 993
    ssl: bool = True
    folders: List[str] = None
    categories: List[Category] = None
    
    def __post_init__(self):
        if self.folders is None:
            self.folders = ["INBOX"]
        
        # Set default categories if none provided
        if self.categories is None:
            self.categories = [
                Category("SPAM", "Unwanted or malicious emails", "Spam"),
                Category("RECEIPTS", "Purchase confirmations and receipts", "[Receipts]"),
                Category("PROMOTIONS", "Marketing and promotional emails", "[Promotions]"),
                Category("UPDATES", "Updates and notifications", "[Updates]"),
                Category("INBOX", "Important emails that need attention", "INBOX")
            ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.email_address})"
    
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