"""Manages IMAP connections and folder operations."""

import email
import logging
import time
from typing import Dict, List, Optional, Tuple, Union

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError, IMAPClientAbortError, IMAPClientReadOnlyError

from .models import Email, EmailAccount

logger = logging.getLogger(__name__)

class IMAPManager:
    """Manages IMAP connections and folder operations."""
    
    def __init__(self):
        """Initialize the IMAP manager."""
        self.connections: Dict[str, Dict] = {}
        self.max_connections = 5  # Limit concurrent connections
        self.connection_timeout = 30  # Seconds to wait before reconnecting
        self._current_folders = {}  # Track currently selected folders
    
    def _clear_response_buffer(self, client: IMAPClient) -> None:
        """Clear the IMAP response buffer."""
        try:
            client._imap._get_response()
        except Exception as e:
            logger.debug(f"Error clearing response buffer: {e}")
    
    def connect(self, account: EmailAccount) -> Optional[IMAPClient]:
        """Connect to an IMAP server.
        
        Args:
            account: The email account to connect to
            
        Returns:
            An IMAPClient object if connection successful, None otherwise
        """
        try:
            # Check if already connected and connection is still valid
            if account.name in self.connections:
                conn_info = self.connections[account.name]
                try:
                    # Try a simple command to check connection
                    conn_info['client'].noop()
                    self._clear_response_buffer(conn_info['client'])
                    conn_info['last_used'] = time.time()
                    return conn_info['client']
                except Exception:
                    # Connection exists but is invalid, clean it up
                    self.disconnect(account.name)
            
            # Clean up old connections if we're at the limit
            if len(self.connections) >= self.max_connections:
                self._cleanup_oldest_connection()
            
            # Create new connection
            logger.debug(f"Connecting to {account}")
            client = IMAPClient(account.imap_server, port=account.imap_port, ssl=account.ssl)
            client.login(account.email_address, account.password)
            self._clear_response_buffer(client)
            
            # Store connection with timestamp
            self.connections[account.name] = {
                'client': client,
                'last_used': time.time(),
                'account': account  # Store account info for reconnection
            }
            self._current_folders[account.name] = None
            logger.debug(f"Connected to {account}")
            return client
        except Exception as e:
            logger.error(f"Error connecting to {account}: {e}")
            if account.name in self.connections:
                self.disconnect(account.name)
            return None
    
    def _cleanup_oldest_connection(self) -> None:
        """Remove the oldest connection to make room for new ones."""
        if not self.connections:
            return
            
        oldest_account = min(
            self.connections.items(),
            key=lambda x: x[1]['last_used']
        )[0]
        
        self.disconnect(oldest_account)
    
    def disconnect(self, account_name: str) -> None:
        """Disconnect from an IMAP server.
        
        Args:
            account_name: Name of the account to disconnect
        """
        try:
            if account_name in self.connections:
                conn_info = self.connections[account_name]
                client = conn_info['client']
                
                # Only try to logout if the connection is still valid
                if client.is_connected():
                    try:
                        client.logout()
                    except Exception as e:
                        logger.warning(f"Error during logout for {account_name}: {e}")
                
                del self.connections[account_name]
                if account_name in self._current_folders:
                    del self._current_folders[account_name]
                logger.debug(f"Disconnected from {account_name}")
        except Exception as e:
            logger.error(f"Error disconnecting from {account_name}: {e}")
            # Ensure connection is removed even if logout fails
            if account_name in self.connections:
                del self.connections[account_name]
            if account_name in self._current_folders:
                del self._current_folders[account_name]
    
    def disconnect_all(self) -> None:
        """Disconnect from all IMAP servers."""
        for account_name in list(self.connections.keys()):
            self.disconnect(account_name)
    
    def _select_folder_if_needed(self, client: IMAPClient, account_name: str, folder: str) -> Tuple[bool, Optional[IMAPClient]]:
        """Select a folder only if it's not already selected.
        
        Args:
            client: IMAP client
            account_name: Account name
            folder: Folder to select
            
        Returns:
            Tuple of (success, new_client if reconnected)
        """
        try:
            current_folder = self._current_folders.get(account_name)
            if current_folder != folder:
                # Check connection before selecting
                try:
                    client.noop()
                    self._clear_response_buffer(client)
                except Exception:
                    # Connection lost, try to reconnect
                    if account_name in self.connections:
                        account = self.connections[account_name]['account']
                        new_client = self.connect(account)
                        if new_client:
                            client = new_client
                        else:
                            return False, None
                
                client.select_folder(folder)
                self._clear_response_buffer(client)
                self._current_folders[account_name] = folder
                logger.debug(f"Selected folder: {folder}")
            return True, client
        except Exception as e:
            logger.error(f"Error selecting folder {folder}: {e}")
            return False, None
    
    def get_emails(
        self, client: IMAPClient, folder: str, max_emails: int
    ) -> Dict[int, Email]:
        """Get all emails from a folder without marking them as read.
        
        Args:
            client: IMAP client
            folder: The folder to get emails from
            max_emails: Maximum number of emails to get
            
        Returns:
            Dictionary mapping message IDs to Email objects
        """
        emails = {}
        
        try:
            # Get account name from client
            account_name = next(
                (name for name, info in self.connections.items() if info['client'] == client),
                None
            )
            if not account_name:
                logger.error("Could not find account for client")
                return emails
            
            # Select folder if needed
            success, new_client = self._select_folder_if_needed(client, account_name, folder)
            if not success:
                return emails
            
            # Get all message IDs
            msg_ids = client.search(['ALL'])
            if not msg_ids:
                logger.debug(f"No emails found in {folder}")
                return emails
            
            # Limit number of emails if specified
            if max_emails > 0:
                msg_ids = msg_ids[-max_emails:]
            
            # Fetch emails in batches to avoid memory issues
            batch_size = 50
            for i in range(0, len(msg_ids), batch_size):
                batch_ids = msg_ids[i:i+batch_size]
                
                try:
                    # Fetch email data
                    raw_emails = client.fetch(batch_ids, ['BODY.PEEK[]'])
                    
                    for msg_id, data in raw_emails.items():
                        try:
                            # Check if the key exists in the data
                            if b'BODY.PEEK[]' not in data:
                                # Try alternative keys that might be returned by the server
                                body_key = None
                                for key in data.keys():
                                    if isinstance(key, bytes) and b'BODY' in key:
                                        body_key = key
                                        break
                                
                                if body_key is None:
                                    logger.error(f"No body data found for email {msg_id}. Available keys: {list(data.keys())}")
                                    continue
                                
                                message = email.message_from_bytes(data[body_key])
                            else:
                                # The key is present as expected
                                message = email.message_from_bytes(data[b'BODY.PEEK[]'])
                            
                            emails[msg_id] = Email.from_message(message, msg_id)
                            emails[msg_id].folder = folder
                        except Exception as e:
                            logger.error(f"Error processing email {msg_id}: {e}")
                    
                    # Clear batch data from memory
                    del raw_emails
                    # Clear response buffer
                    self._clear_response_buffer(client)
                    
                except Exception as e:
                    logger.error(f"Error fetching batch: {e}")
                    continue
            
            logger.debug(f"Successfully processed {len(emails)} emails from {folder} without marking as read")
            return emails
        except Exception as e:
            logger.error(f"Error fetching emails from {folder}: {e}")
            return {}
    
    def ensure_folder_exists(self, client: IMAPClient, folder: str) -> None:
        """Ensure a folder exists, create it if it doesn't.
        
        Args:
            client: The IMAPClient object
            folder: The folder name to check/create
        """
        folders = [f.decode() if isinstance(f, bytes) else f for f in client.list_folders()]
        folder_names = [f[2] for f in folders]
        
        if folder not in folder_names:
            logger.debug(f"Creating folder: {folder}")
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
                    logger.debug(f"Preserved unread status for {len(messages)} emails in {target_folder}")
            
            return True
        except Exception as e:
            logger.error(f"Error moving email {msg_id} to {target_folder}: {e}")
            return False 