"""Data models for email processing."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from email.message import Message

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
    
    def __post_init__(self):
        if self.folders is None:
            self.folders = ["INBOX"]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.email_address})"

@dataclass
class ProcessingOptions:
    """Configuration options for email processing."""
    max_emails_per_run: int = 100
    batch_size: int = 10
    idle_timeout: int = 1740  # 29 minutes
    move_emails: bool = True
    category_folders: dict = None
    custom_categories: List[str] = None
    
    def __post_init__(self):
        if self.category_folders is None:
            self.category_folders = {
                "spam": "[Spam]",
                "receipts": "[Receipts]",
                "promotions": "[Promotions]",
                "updates": "[Updates]",
                "inbox": "INBOX",
            }
        
        if self.custom_categories is None:
            self.custom_categories = ["SPAM", "RECEIPTS", "PROMOTIONS", "UPDATES", "INBOX"] 