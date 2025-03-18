"""Download emails from IMAP server for training data."""

import os
import logging
import imaplib
import email
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from email.message import Message

logger = logging.getLogger(__name__)

class IMAPDownloader:
    """Download emails from IMAP server."""
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 993,
        use_ssl: bool = True,
        config_path: Optional[str] = None
    ):
        """Initialize IMAP connection.
        
        Args:
            host: IMAP server hostname
            username: IMAP account username
            password: IMAP account password
            port: IMAP server port
            use_ssl: Whether to use SSL
            config_path: Path to config file
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.conn = None
        self.config = self._load_config(config_path) if config_path else None
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return None
    
    def _get_folder_mapping(self) -> Dict[str, str]:
        """Get folder mapping from config or defaults."""
        if self.config and 'accounts' in self.config:
            # Find the matching account
            account = next(
                (acc for acc in self.config['accounts'] 
                 if acc['email'] == self.username),
                None
            )
            
            if account and 'categories' in account:
                # Use the account's category mapping
                return {
                    cat['foldername']: cat['name']
                    for cat in account['categories']
                }
        
        # Default mapping if no config or account not found
        return {
            "INBOX": "INBOX",
            "Junk": "SPAM",
            "@Promotions": "PROMOTIONS",
            "@Receipts": "RECEIPTS",
            "@Updates": "UPDATES"
        }
    
    def _get_category_from_flags(self, flags: List[str]) -> Optional[str]:
        """Extract category from IMAP flags."""
        flag_mapping = {
            "$label1": "PROMOTIONS",
            "$label2": "UPDATES",
            "$label3": "RECEIPTS",
            "$label4": "SPAM",
            "\\Junk": "SPAM",
            "@promotions": "PROMOTIONS",
            "@updates": "UPDATES",
            "@receipts": "RECEIPTS"
        }
        
        # Convert flags to lowercase for case-insensitive matching
        flags_lower = [f.lower() for f in flags]
        
        # Check each flag
        for flag in flags:
            flag_lower = flag.lower()
            # Direct mapping
            if flag in flag_mapping:
                return flag_mapping[flag]
            # Check for keywords/labels
            for keyword, category in flag_mapping.items():
                if keyword.lower() in flag_lower:
                    return category
        
        return None
    
    def _get_category_from_headers(self, msg: Message) -> Optional[str]:
        """Extract category from email headers."""
        # Check X-Keywords header
        keywords = msg.get("x-keywords", "").lower()
        if "spam" in keywords or "junk" in keywords:
            return "SPAM"
        if "promotion" in keywords:
            return "PROMOTIONS"
        if "receipt" in keywords or "order" in keywords:
            return "RECEIPTS"
        if "update" in keywords:
            return "UPDATES"
        
        # Check other headers that might indicate category
        subject = msg.get("subject", "").lower()
        if any(word in subject for word in ["receipt", "order confirmation", "invoice"]):
            return "RECEIPTS"
        if any(word in subject for word in ["off", "sale", "discount", "deal"]):
            return "PROMOTIONS"
        if any(word in subject for word in ["update", "notification", "alert"]):
            return "UPDATES"
        
        return None
    
    def connect(self) -> None:
        """Connect to IMAP server."""
        try:
            if self.use_ssl:
                self.conn = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self.conn = imaplib.IMAP4(self.host, self.port)
            
            self.conn.login(self.username, self.password)
            logger.info(f"Connected to {self.host} as {self.username}")
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise
    
    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self.conn:
            try:
                self.conn.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error disconnecting from IMAP server: {e}")
    
    def list_folders(self) -> List[str]:
        """List available folders/mailboxes.
        
        Returns:
            List of folder names
        """
        if not self.conn:
            self.connect()
        
        try:
            _, folders = self.conn.list()
            folder_names = []
            
            for folder in folders:
                # Parse folder name from response
                parts = folder.decode().split('"/"')
                if len(parts) > 1:
                    folder_name = parts[1].strip().strip('"')
                    folder_names.append(folder_name)
            
            return folder_names
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            raise
    
    def _fetch_email_with_flags(self, num: bytes) -> Tuple[Optional[bytes], List[str]]:
        """Fetch email and its flags."""
        try:
            # Fetch flags
            _, flag_data = self.conn.fetch(num, '(FLAGS)')
            flags = []
            if flag_data[0]:
                # Extract flags from response
                flag_str = flag_data[0].decode()
                flags = [f.strip() for f in flag_str[flag_str.find("(")+1:flag_str.find(")")].split()]
            
            # Fetch email
            _, msg_data = self.conn.fetch(num, '(RFC822)')
            if msg_data[0]:
                return msg_data[0][1], flags
            return None, flags
        except Exception as e:
            logger.error(f"Error fetching email {num}: {e}")
            return None, []
    
    def download_emails(
        self,
        output_dir: str,
        folders: Optional[Dict[str, str]] = None,
        max_emails: int = 100,
        include_archive: bool = True
    ) -> None:
        """Download emails from specified folders.
        
        Args:
            output_dir: Directory to save emails
            folders: Dictionary mapping IMAP folders to local category names
                    If None, uses default mapping
            max_emails: Maximum number of emails to download per folder
            include_archive: Whether to include emails from the Archive folder
        """
        if not self.conn:
            self.connect()
        
        # Default folder mapping if none provided
        if folders is None:
            folders = self._get_folder_mapping()
        
        output_dir = Path(output_dir)
        
        # First download from regular folders
        for imap_folder, category in folders.items():
            try:
                # Select folder
                self.conn.select(imap_folder, readonly=True)
                
                # Search for all emails
                _, message_numbers = self.conn.search(None, "ALL")
                message_list = message_numbers[0].split()
                
                # Create category directory
                category_dir = output_dir / category
                category_dir.mkdir(parents=True, exist_ok=True)
                
                # Download most recent emails up to max_emails
                for i, num in enumerate(reversed(message_list)):
                    if i >= max_emails:
                        break
                    
                    try:
                        email_body, _ = self._fetch_email_with_flags(num)
                        if email_body:
                            msg = email.message_from_bytes(email_body)
                            
                            # Generate filename from subject or message ID
                            subject = msg.get("subject", "")
                            msg_id = msg.get("message-id", "").strip("<>")
                            filename = f"{i+1}_{subject[:30] or msg_id[:30]}.eml"
                            filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                            
                            # Save email
                            email_path = category_dir / filename
                            with open(email_path, "wb") as f:
                                f.write(email_body)
                            
                            logger.info(f"Downloaded email to {email_path}")
                    except Exception as e:
                        logger.error(f"Error downloading email {num}: {e}")
                        continue
                
                logger.info(f"Downloaded {min(max_emails, len(message_list))} emails from {imap_folder}")
            except Exception as e:
                logger.error(f"Error processing folder {imap_folder}: {e}")
                continue
        
        # Then check Archive folder if requested
        if include_archive:
            try:
                self.conn.select("Archive", readonly=True)
                _, message_numbers = self.conn.search(None, "ALL")
                message_list = message_numbers[0].split()
                
                for i, num in enumerate(reversed(message_list)):
                    if i >= max_emails:
                        break
                    
                    try:
                        email_body, flags = self._fetch_email_with_flags(num)
                        if not email_body:
                            continue
                        
                        msg = email.message_from_bytes(email_body)
                        
                        # Try to determine category
                        category = (
                            self._get_category_from_flags(flags) or 
                            self._get_category_from_headers(msg)
                        )
                        
                        if category:
                            category_dir = output_dir / category
                            category_dir.mkdir(parents=True, exist_ok=True)
                            
                            subject = msg.get("subject", "")
                            msg_id = msg.get("message-id", "").strip("<>")
                            filename = f"archive_{i+1}_{subject[:30] or msg_id[:30]}.eml"
                            filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                            
                            email_path = category_dir / filename
                            with open(email_path, "wb") as f:
                                f.write(email_body)
                            
                            logger.info(f"Downloaded archived email to {email_path}")
                    except Exception as e:
                        logger.error(f"Error downloading archived email {num}: {e}")
                        continue
                
                logger.info(f"Finished processing Archive folder")
            except Exception as e:
                logger.error(f"Error processing Archive folder: {e}")
        
        self.disconnect() 