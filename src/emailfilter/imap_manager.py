"""Manages IMAP connections and folder operations."""

import email
import logging
from typing import Dict, List, Optional, Tuple

from imapclient import IMAPClient

from .models import Email, EmailAccount

logger = logging.getLogger(__name__)

class IMAPManager:
    """Manages IMAP connections and folder operations."""
    
    def __init__(self):
        """Initialize the IMAP manager."""
        self.connections: Dict[str, IMAPClient] = {}
    
    def connect(self, account: EmailAccount) -> Optional[IMAPClient]:
        """Connect to an IMAP server.
        
        Args:
            account: The email account to connect to
            
        Returns:
            An IMAPClient object if connection successful, None otherwise
        """
        try:
            # Check if already connected
            if account.name in self.connections and self.connections[account.name].is_connected:
                logger.info(f"Already connected to {account}")
                return self.connections[account.name]
            
            # Create new connection
            logger.info(f"Connecting to {account}")
            client = IMAPClient(account.imap_server, port=account.imap_port, ssl=account.ssl)
            client.login(account.email_address, account.password)
            
            # Store connection
            self.connections[account.name] = client
            logger.info(f"Connected to {account}")
            return client
        except Exception as e:
            logger.error(f"Error connecting to {account}: {e}")
            return None
    
    def disconnect(self, account_name: str) -> None:
        """Disconnect from an IMAP server.
        
        Args:
            account_name: Name of the account to disconnect from
        """
        if account_name in self.connections:
            try:
                self.connections[account_name].logout()
                logger.info(f"Disconnected from {account_name}")
            except Exception as e:
                logger.error(f"Error disconnecting from {account_name}: {e}")
            finally:
                del self.connections[account_name]
    
    def disconnect_all(self) -> None:
        """Disconnect from all IMAP servers."""
        for account_name in list(self.connections.keys()):
            self.disconnect(account_name)
    
    def ensure_folder_exists(self, client: IMAPClient, folder: str) -> None:
        """Ensure a folder exists, create it if it doesn't.
        
        Args:
            client: The IMAPClient object
            folder: The folder name to check/create
        """
        folders = [f.decode() if isinstance(f, bytes) else f for f in client.list_folders()]
        folder_names = [f[2] for f in folders]
        
        if folder not in folder_names:
            logger.info(f"Creating folder: {folder}")
            client.create_folder(folder)
    
    def move_email(self, client: IMAPClient, msg_id: int, target_folder: str) -> bool:
        """Move an email to a target folder without changing its read/unread status.
        
        Args:
            client: The IMAPClient object
            msg_id: The message ID to move
            target_folder: The target folder to move to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure target folder exists
            self.ensure_folder_exists(client, target_folder)
            
            # Check if the message is unread before moving
            response = client.fetch([msg_id], ['FLAGS', 'ENVELOPE'])
            is_unread = b'\\Seen' not in response[msg_id][b'FLAGS']
            
            # Get message identifiers to find it after moving
            envelope = response[msg_id][b'ENVELOPE']
            message_id = envelope.message_id
            subject = envelope.subject
            date = envelope.date
            
            # Move the message
            client.move(msg_id, target_folder)
            logger.info(f"Moved email {msg_id} to {target_folder}")
            
            # If the message was unread, make sure it stays unread in the target folder
            if is_unread:
                # Select the target folder
                client.select_folder(target_folder)
                
                # Search for the message in the target folder using message-id header
                if message_id:
                    # Search by Message-ID header
                    search_criteria = ['HEADER', 'Message-ID', message_id.decode('utf-8', errors='ignore')]
                    messages = client.search(search_criteria)
                elif subject and date:
                    # Fallback: search by subject and date
                    subject_str = subject.decode('utf-8', errors='ignore') if isinstance(subject, bytes) else str(subject)
                    search_criteria = ['SUBJECT', subject_str]
                    messages = client.search(search_criteria)
                else:
                    # Last resort: get recent messages
                    messages = client.search(['RECENT'])
                
                if messages:
                    # Remove the Seen flag to keep it unread
                    client.remove_flags(messages, [b'\\Seen'])
                    logger.info(f"Preserved unread status for {len(messages)} emails in {target_folder}")
            
            return True
        except Exception as e:
            logger.error(f"Error moving email {msg_id} to {target_folder}: {e}")
            return False
    
    def get_emails(
        self, client: IMAPClient, folder: str, max_emails: int
    ) -> Dict[int, Email]:
        """Get all emails from a folder.
        
        Args:
            client: The IMAPClient object
            folder: The folder to fetch emails from
            max_emails: Maximum number of emails to fetch
            
        Returns:
            Dictionary mapping message IDs to Email objects
        """
        try:
            # Select the folder
            client.select_folder(folder)
            logger.info(f"Selected folder: {folder}")
            
            # Search for all emails in the folder
            messages = client.search(['ALL'])
            logger.info(f"Found {len(messages)} emails in {folder}")
            
            # Sort messages by ID (higher IDs are more recent)
            messages.sort(reverse=True)
            
            # Limit the number of emails (most recent first)
            if max_emails > 0 and len(messages) > max_emails:
                logger.info(f"Limiting to {max_emails} most recent emails")
                messages = messages[:max_emails]
            
            # Fetch email data
            if not messages:
                logger.info(f"No messages to fetch from {folder}")
                return {}
            
            logger.info(f"Fetching {len(messages)} emails from {folder}")
            raw_emails = client.fetch(messages, ['ENVELOPE', 'BODY[]'])
            
            # Convert to Email objects
            emails = {}
            for msg_id, data in raw_emails.items():
                try:
                    message = email.message_from_bytes(data[b'BODY[]'])
                    emails[msg_id] = Email.from_message(message, msg_id)
                    emails[msg_id].folder = folder
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {e}")
            
            logger.info(f"Successfully processed {len(emails)} emails from {folder}")
            return emails
        except Exception as e:
            logger.error(f"Error fetching emails from {folder}: {e}")
            return {} 