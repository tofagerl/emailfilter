"""Data loading and preprocessing for email categorization training."""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import email
import json
from email.parser import BytesParser
from email.policy import default
import chardet

import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizer

logger = logging.getLogger(__name__)

class EmailDataset(Dataset):
    """Dataset for email categorization."""
    
    def __init__(
        self,
        data_dir: str,
        tokenizer: Optional[PreTrainedTokenizer] = None,
        max_length: int = 512
    ):
        """Initialize the dataset.
        
        Args:
            data_dir: Directory containing categorized email files
            tokenizer: Tokenizer to use
            max_length: Maximum sequence length
        """
        self.data_dir = Path(data_dir)
        self.tokenizer = tokenizer
        self.max_length = max_length
        
        # Get categories from directory names
        categories = [d.name for d in self.data_dir.iterdir() if d.is_dir()]
        
        # Create category mappings
        self.category_to_id = {cat: i for i, cat in enumerate(sorted(categories))}
        self.id_to_category = {i: cat for cat, i in self.category_to_id.items()}
        
        # Load emails and labels
        self.emails = []
        self.labels = []
        
        # Load all emails
        for category in categories:
            category_dir = self.data_dir / category
            if not category_dir.is_dir():
                continue
            
            for email_file in category_dir.glob("*.eml"):
                try:
                    email_content = self._read_email_file(email_file)
                    if email_content is None:
                        continue
                    
                    # Parse email
                    msg = email.message_from_string(email_content)
                    
                    # Extract fields
                    email_dict = {
                        "from": self._decode_header(msg.get("from", "")),
                        "to": self._decode_header(msg.get("to", "")),
                        "subject": self._decode_header(msg.get("subject", "")),
                        "date": msg.get("date", ""),
                        "body": self._get_email_body(msg)
                    }
                    
                    self.emails.append(email_dict)
                    self.labels.append(self.category_to_id[category])
                except Exception as e:
                    logger.error(f"Error loading email {email_file}: {e}")
        
        logger.info(
            f"Loaded {len(self.emails)} emails from {len(self.category_to_id)} categories: "
            f"{', '.join(self.category_to_id.keys())}"
        )
    
    def _read_email_file(self, file_path: Path) -> Optional[str]:
        """Read email file with encoding detection."""
        try:
            # First try UTF-8
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                # Try to detect encoding
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                    result = chardet.detect(raw_data)
                    encoding = result["encoding"] or "latin1"
                
                # Try detected encoding
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read {file_path} with detected encoding {encoding}: {e}")
                return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header properly."""
        try:
            decoded = email.header.decode_header(header)
            parts = []
            for text, charset in decoded:
                if isinstance(text, bytes):
                    try:
                        if charset:
                            text = text.decode(charset)
                        else:
                            text = text.decode("utf-8")
                    except:
                        text = text.decode("latin1", errors="replace")
                parts.append(str(text))
            return " ".join(parts)
        except:
            return header
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract the body text from an email message."""
        body = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            decoded = payload.decode(charset)
                        except:
                            decoded = payload.decode("latin1", errors="replace")
                        body.append(decoded)
                    except:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset)
                except:
                    decoded = payload.decode("latin1", errors="replace")
                body.append(decoded)
            except:
                pass
        return "\n".join(body)
    
    def _prepare_email_text(self, email_dict: Dict[str, str]) -> str:
        """Prepare email text for the model.
        
        Args:
            email_dict: Dictionary containing email fields
            
        Returns:
            Formatted email text
        """
        return f"""From: {email_dict['from']}
To: {email_dict['to']}
Subject: {email_dict['subject']}
Date: {email_dict['date']}
Body: {email_dict['body']}"""
    
    def __len__(self) -> int:
        """Get the number of emails in the dataset."""
        return len(self.emails)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get an email and its label.
        
        Args:
            idx: Index of the email
            
        Returns:
            Dictionary containing input_ids, attention_mask, and labels
        """
        email_dict = self.emails[idx]
        label = self.labels[idx]
        
        # Prepare text
        text = self._prepare_email_text(email_dict)
        
        # Tokenize
        if self.tokenizer is None:
            raise ValueError("Tokenizer not set")
        
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        # Remove batch dimension added by tokenizer
        encoding = {k: v.squeeze(0) for k, v in encoding.items()}
        
        # Add label
        encoding["labels"] = torch.tensor(label)
        
        return encoding 