"""Manages IMAP connections and folder operations."""

import email
import logging
import time
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError, IMAPClientAbortError, IMAPClientReadOnlyError
import imaplib

from .models import Email, EmailAccount

logger = logging.getLogger(__name__)

class IMAPManager:
    """Manages IMAP connections and folder operations."""
    
    def __init__(self):
        """Initialize the IMAP manager."""
        self.client = None
        self.current_folder = None
        self.connections = {}
        self._current_folders = {}
        self.max_connections = 5  # Limit concurrent connections
        self.connection_timeout = 30  # Seconds to wait before reconnecting
        self.logger = logging.getLogger(__name__)
    
    def connect(self, account: EmailAccount) -> Optional[IMAPClient]:
        """Connect to an IMAP server.
        
        Args:
            account: The email account to connect to
            
        Returns:
            The IMAPClient object if connection successful, None otherwise
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
            client = IMAPClient(account.imap_server, port=account.imap_port, ssl=True)
            client.login(account.email, account.password)
            
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

    def disconnect(self):
        """Disconnect from the IMAP server."""
        if self.client:
            try:
                response = self.client.logout()
                if response[0] != 'OK':
                    self.logger.error(f"Failed to logout: {response[1]}")
                self.client = None
                self.current_folder = None
                self.logger.info("Disconnected from IMAP server")
            except Exception as e:
                self.logger.error(f"Error during IMAP disconnect: {str(e)}")

    def _select_folder_if_needed(self, folder_name):
        """Select a folder if it's not already selected."""
        if not self.connections:
            logger.error("Not connected to IMAP server")
            return False
        
        # Get the first connection (we only support one account for now)
        client = next(iter(self.connections.values()))['client']
        
        if self._current_folders.get(next(iter(self.connections.keys()))) != folder_name:
            try:
                client.select_folder(folder_name)
                self._current_folders[next(iter(self.connections.keys()))] = folder_name
                return True
            except Exception as e:
                logger.error(f"Failed to select folder {folder_name}: {str(e)}")
                return False
        return True

    def fetch_emails_from_folder(self, folder_name, since=None):
        """Fetch emails from a specific folder since a given date.
        
        Args:
            folder_name (str): Name of the folder to fetch from
            since (datetime): Only fetch emails after this date
            
        Returns:
            list[Email]: List of Email objects sorted by date
        """
        if not self.connections:
            logger.error("Not connected to IMAP server")
            return []

        try:
            if not self._select_folder_if_needed(folder_name):
                return []

            search_criteria = []
            if since:
                date_str = since.strftime("%d-%b-%Y")
                search_criteria.extend(['SINCE', date_str])

            # Get the first connection (we only support one account for now)
            client = next(iter(self.connections.values()))['client']
            message_ids = client.search(search_criteria)
            if not message_ids:
                return []

            emails = []
            for msg_id in message_ids:
                try:
                    msg_data = client.fetch([msg_id], ['BODY.PEEK[]', 'FLAGS', 'ENVELOPE'])
                    if not msg_data:
                        logger.error(f"Failed to fetch email {msg_id}")
                        continue

                    msg_data = msg_data[msg_id]
                    msg = email.message_from_bytes(msg_data[b'BODY.PEEK[]'])
                    envelope = msg_data.get(b'ENVELOPE')
                    
                    if envelope and envelope[0]:
                        try:
                            msg_date = datetime.strptime(
                                envelope[0].decode(), 
                                '%a, %d %b %Y %H:%M:%S %z'
                            )
                        except ValueError:
                            try:
                                msg_date = datetime.strptime(
                                    envelope[0].decode(), 
                                    '%a, %d %b %Y %H:%M:%S +0000'
                                )
                            except ValueError:
                                msg_date = datetime.now()
                    else:
                        msg_date = datetime.now()

                    email_obj = Email(
                        subject=msg.get('Subject', ''),
                        from_addr=msg.get('From', ''),
                        to_addr=msg.get('To', ''),
                        body=self._get_email_body(msg),
                        date=msg_date,
                        raw_message=msg.as_bytes(),
                        message_id=msg.get('Message-ID', ''),
                        folder=folder_name
                    )
                    
                    emails.append(email_obj)
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {str(e)}")
                    continue

            return sorted(emails, key=lambda x: x.date)

        except Exception as e:
            logger.error(f"Error fetching emails from folder {folder_name}: {str(e)}")
            return []

    def _get_email_body(self, msg):
        """Extract the email body from a message."""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True)
                            return body.decode('utf-8', errors='ignore') if body else ""
                        except Exception as e:
                            logger.error(f"Error decoding email part: {e}")
                            continue
            
            # If no text/plain part found or not multipart
            body = msg.get_payload(decode=True)
            return body.decode('utf-8', errors='ignore') if body else ""
        except Exception as e:
            logger.error(f"Error extracting email body: {e}")
            return ""

    def _clear_response_buffer(self, client: IMAPClient) -> None:
        """Clear the IMAP response buffer."""
        try:
            client._imap._get_response()
        except Exception as e:
            logger.debug(f"Error clearing response buffer: {e}")
    
    def _cleanup_oldest_connection(self) -> None:
        """Remove the oldest connection to make room for new ones."""
        if not self.connections:
            return
            
        oldest_account = min(
            self.connections.items(),
            key=lambda x: x[1]['last_used']
        )[0]
        
        self.disconnect(oldest_account)
    
    def _is_connection_alive(self, client: IMAPClient) -> bool:
        """Check if the IMAP connection is still alive.
        
        Args:
            client: The IMAPClient object
            
        Returns:
            True if connection is alive, False otherwise
        """
        try:
            client.noop()
            return True
        except Exception:
            return False

    def disconnect(self, account_name: str) -> None:
        """Disconnect from an IMAP server.
        
        Args:
            account_name: Name of the account to disconnect
        """
        try:
            if account_name in self.connections:
                conn_info = self.connections[account_name]
                client = conn_info['client']
                
                # Try to end any active IDLE sessions
                try:
                    client.idle_done()
                except Exception:
                    pass  # Ignore errors when ending IDLE
                
                # Only try to logout if the connection appears alive
                if self._is_connection_alive(client):
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
        # Create a list of account names to avoid modifying dict during iteration
        account_names = list(self.connections.keys())
        for account_name in account_names:
            self.disconnect(account_name)
    
    def get_emails(self, client: IMAPClient, folder: str, max_emails: int = 0) -> Dict[int, Email]:
        """Get emails from a folder.
        
        Args:
            client: The IMAPClient object
            folder: The folder to get emails from
            max_emails: Maximum number of emails to get (0 for no limit)
            
        Returns:
            Dictionary mapping message IDs to Email objects
        """
        try:
            # Select folder
            client.select_folder(folder)
            
            # Search for all emails
            message_ids = client.search(['ALL'])
            if not message_ids:
                return {}
            
            # Limit number of emails if specified
            if max_emails > 0:
                message_ids = message_ids[-max_emails:]
            
            emails = {}
            batch_size = 100  # Process in batches to manage memory
            
            for i in range(0, len(message_ids), batch_size):
                batch_ids = message_ids[i:i+batch_size]
                try:
                    # Fetch email data
                    raw_emails = client.fetch(batch_ids, ['RFC822', 'FLAGS', 'ENVELOPE'])
                    
                    for msg_id, data in raw_emails.items():
                        try:
                            # Extract message data
                            raw_message = data[b'RFC822']
                            message = email.message_from_bytes(raw_message)
                            envelope = data[b'ENVELOPE']
                            
                            # Get date from envelope or fallback to message date
                            if envelope and envelope.date:
                                try:
                                    msg_date = datetime.strptime(
                                        envelope.date.decode('utf-8', errors='ignore'),
                                        '%a, %d %b %Y %H:%M:%S %z'
                                    )
                                except (ValueError, AttributeError):
                                    msg_date = datetime.now()
                            else:
                                msg_date = datetime.now()
                            
                            # Create Email object
                            email_obj = Email(
                                subject=message['Subject'],
                                from_addr=message['From'],
                                to_addr=message['To'],
                                body=self._get_email_body(message),
                                date=msg_date,
                                raw_message=message.as_bytes(),
                                message_id=message['Message-ID'],
                                folder=folder
                            )
                            emails[msg_id] = email_obj
                        except Exception as e:
                            logger.error(f"Error processing email {msg_id}: {e}")
                            continue
                    
                    # Clear batch data from memory
                    del raw_emails
                    
                except Exception as e:
                    logger.error(f"Error fetching batch: {e}")
                    continue
            
            return emails
        except Exception as e:
            logger.error(f"Error getting emails from {folder}: {e}")
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
            logger.debug(f"Starting to move email {msg_id} to {target_folder}")
            
            # Ensure target folder exists
            self.ensure_folder_exists(client, target_folder)
            logger.debug(f"Target folder {target_folder} exists or was created")
            
            # Check if the message is unread before moving
            response = client.fetch([msg_id], ['FLAGS', 'ENVELOPE'])
            is_unread = b'\\Seen' not in response[msg_id][b'FLAGS']
            logger.debug(f"Email {msg_id} unread status: {is_unread}")
            
            # Get message identifiers to find it after moving
            envelope = response[msg_id][b'ENVELOPE']
            message_id = envelope.message_id
            subject = envelope.subject
            date = envelope.date
            logger.debug(f"Email {msg_id} identifiers - Message-ID: {message_id}, Subject: {subject}, Date: {date}")
            
            # Move the message
            client.move(msg_id, target_folder)
            logger.info(f"Moved email {msg_id} to {target_folder}")
            
            # If the message was unread, make sure it stays unread in the target folder
            if is_unread:
                logger.debug(f"Preserving unread status for email {msg_id} in {target_folder}")
                # Select the target folder
                client.select_folder(target_folder)
                
                # Search for the message in the target folder using message-id header
                if message_id:
                    # Search by Message-ID header
                    search_criteria = ['HEADER', 'Message-ID', message_id.decode('utf-8', errors='ignore')]
                    messages = client.search(search_criteria)
                    logger.debug(f"Searching for email by Message-ID: {message_id}")
                elif subject and date:
                    # Fallback: search by subject and date
                    subject_str = subject.decode('utf-8', errors='ignore') if isinstance(subject, bytes) else str(subject)
                    search_criteria = ['SUBJECT', subject_str]
                    messages = client.search(search_criteria)
                    logger.debug(f"Searching for email by subject: {subject_str}")
                else:
                    # Last resort: get recent messages
                    messages = client.search(['RECENT'])
                    logger.debug("Searching for email in recent messages")
                
                if messages:
                    # Remove the Seen flag to keep it unread
                    client.remove_flags(messages, [b'\\Seen'])
                    logger.debug(f"Preserved unread status for {len(messages)} emails in {target_folder}")
                else:
                    logger.debug(f"Could not find email {msg_id} in target folder {target_folder} to preserve unread status")
            
            return True
        except Exception as e:
            logger.error(f"Error moving email {msg_id} to {target_folder}: {e}")
            return False 