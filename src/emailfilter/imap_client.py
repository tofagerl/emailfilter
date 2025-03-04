"""IMAP client for fetching and processing emails."""

import email
import email.header
import email.utils
import logging
import os
import re
import signal
import sys
import threading
import time
import json
import hashlib
from datetime import datetime, timedelta
from email.message import Message
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml
from imapclient import IMAPClient

from emailfilter import categorizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout  # Explicitly use stdout
)
logger = logging.getLogger(__name__)

# Global flag for controlling the continuous monitoring
running = True


class EmailAccount:
    """Class representing an email account configuration."""

    def __init__(
        self,
        name: str,
        email_address: str,
        password: str,
        imap_server: str,
        imap_port: int = 993,
        ssl: bool = True,
        folders: Optional[List[str]] = None,
    ):
        """Initialize an email account configuration.

        Args:
            name: A friendly name for the account
            email_address: The email address
            password: The password or app password
            imap_server: The IMAP server hostname
            imap_port: The IMAP server port
            ssl: Whether to use SSL
            folders: List of folders to process
        """
        self.name = name
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.ssl = ssl
        self.folders = folders or ["INBOX"]

    def __str__(self) -> str:
        """Return a string representation of the account."""
        return f"{self.name} ({self.email_address})"


class EmailProcessor:
    """Class for processing emails from IMAP accounts."""

    def __init__(self, config_path: str):
        """Initialize the email processor.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.accounts = []
        self.options = {}
        self.processed_state = {}
        self.state_file_path = os.path.expanduser("~/.emailfilter/processed_emails.json")
        
        # Create directory for state file if it doesn't exist
        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        
        # Load configuration
        self._load_config()
        
        # Load processed emails state
        self._load_processed_state()
        
        # Load OpenAI API key from config
        try:
            categorizer.load_api_key(self.config_path)
        except ValueError as e:
            logger.error(f"Error loading OpenAI API key: {e}")
            raise

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Load accounts
            for account_config in config.get("accounts", []):
                account = EmailAccount(
                    name=account_config.get("name", ""),
                    email_address=account_config.get("email", ""),
                    password=account_config.get("password", ""),
                    imap_server=account_config.get("imap_server", ""),
                    imap_port=account_config.get("imap_port", 993),
                    ssl=account_config.get("ssl", True),
                    folders=account_config.get("folders", ["INBOX"]),
                )
                self.accounts.append(account)

            # Load options
            self.options = config.get("options", {})

            logger.info(f"Loaded configuration with {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _load_processed_state(self) -> None:
        """Load processed emails state from JSON file."""
        try:
            if os.path.exists(self.state_file_path):
                with open(self.state_file_path, "r") as f:
                    self.processed_state = json.load(f)
                logger.info(f"Loaded processed state with {sum(len(ids) for ids in self.processed_state.values())} emails")
            else:
                self.processed_state = {}
                logger.info("No existing processed state found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading processed state: {e}")
            self.processed_state = {}

    def _save_processed_state(self) -> None:
        """Save processed emails state to JSON file."""
        try:
            with open(self.state_file_path, "w") as f:
                json.dump(self.processed_state, f)
            logger.info(f"Saved processed state with {sum(len(ids) for ids in self.processed_state.values())} emails")
        except Exception as e:
            logger.error(f"Error saving processed state: {e}")

    def _generate_email_id(self, account_name: str, msg_id: int, email_data: Dict[str, Any]) -> str:
        """Generate a unique ID for an email.
        
        Args:
            account_name: Name of the email account
            msg_id: IMAP message ID
            email_data: Email data dictionary
            
        Returns:
            A unique string ID for the email
        """
        # Create a unique identifier using account, message ID, and email metadata
        unique_str = f"{account_name}:{msg_id}:{email_data.get('from', '')}:{email_data.get('subject', '')}:{email_data.get('date', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def _is_email_processed(self, account_name: str, msg_id: int, email_data: Dict[str, Any]) -> bool:
        """Check if an email has been processed.
        
        Args:
            account_name: Name of the email account
            msg_id: IMAP message ID
            email_data: Email data dictionary
            
        Returns:
            True if the email has been processed, False otherwise
        """
        email_id = self._generate_email_id(account_name, msg_id, email_data)
        return account_name in self.processed_state and email_id in self.processed_state[account_name]

    def _mark_email_as_processed(self, account_name: str, msg_id: int, email_data: Dict[str, Any]) -> None:
        """Mark an email as processed in the local state.
        
        Args:
            account_name: Name of the email account
            msg_id: IMAP message ID
            email_data: Email data dictionary
        """
        email_id = self._generate_email_id(account_name, msg_id, email_data)
        
        # Initialize account in state if not exists
        if account_name not in self.processed_state:
            self.processed_state[account_name] = []
            
        # Add email ID to processed state
        self.processed_state[account_name].append(email_id)
        
        # Save state after each update
        self._save_processed_state()

    def _cleanup_processed_state(self, max_age_days: int = 30) -> None:
        """Clean up old entries from the processed state.
        
        Args:
            max_age_days: Maximum age of entries in days
        """
        # Not implemented in this version since we're using a simple list
        # In a more advanced implementation, we would store timestamps with each entry
        # and remove entries older than max_age_days
        
        # For now, just limit the size of each account's list
        max_entries = 10000  # Adjust as needed
        for account_name in self.processed_state:
            if len(self.processed_state[account_name]) > max_entries:
                # Keep only the most recent entries
                self.processed_state[account_name] = self.processed_state[account_name][-max_entries:]
        
        # Save the cleaned up state
        self._save_processed_state()

    def connect_to_account(self, account: EmailAccount) -> Optional[IMAPClient]:
        """Connect to an IMAP account.

        Args:
            account: The EmailAccount to connect to

        Returns:
            IMAPClient object or None if connection failed
        """
        try:
            logger.info(f"Connecting to {account.imap_server}:{account.imap_port}")
            client = IMAPClient(account.imap_server, port=account.imap_port, ssl=account.ssl)
            client.login(account.email_address, account.password)
            logger.info(f"Connected to {account}")
            return client
        except Exception as e:
            logger.error(f"Error connecting to {account}: {e}")
            return None

    def get_unprocessed_emails(
        self, client: IMAPClient, folder: str, max_emails: int, account_name: str
    ) -> Dict[int, Dict[str, Any]]:
        """Get unprocessed emails from a folder.

        Args:
            client: The IMAPClient object
            folder: The folder to fetch emails from
            max_emails: Maximum number of emails to fetch
            account_name: Name of the email account

        Returns:
            Dictionary mapping message IDs to email data
        """
        try:
            client.select_folder(folder)
            
            # Search for all emails
            messages = client.search(["ALL"])
            
            # Limit the number of messages
            messages = messages[:max_emails]
            
            if not messages:
                logger.info(f"No emails found in {folder}")
                return {}
            
            logger.info(f"Found {len(messages)} emails in {folder}")
            
            # Fetch email data
            email_data = {}
            for msg_id, data in client.fetch(messages, ["ENVELOPE", "RFC822"]).items():
                try:
                    raw_message = data[b"RFC822"]
                    parsed_email = email.message_from_bytes(raw_message)
                    
                    # Extract email parts
                    subject = self._decode_header(parsed_email["Subject"] or "")
                    from_addr = self._decode_header(parsed_email["From"] or "")
                    to_addr = self._decode_header(parsed_email["To"] or "")
                    date = parsed_email["Date"] or ""
                    body = self._get_email_body(parsed_email)
                    
                    email_info = {
                        "subject": subject,
                        "from": from_addr,
                        "to": to_addr,
                        "date": date,
                        "body": body,
                        "raw_message": raw_message,
                    }
                    
                    # Check if this email has been processed before
                    if not self._is_email_processed(account_name, msg_id, email_info):
                        email_data[msg_id] = email_info
                except Exception as e:
                    logger.error(f"Error processing message {msg_id}: {e}")
            
            logger.info(f"Found {len(email_data)} unprocessed emails in {folder}")
            return email_data
        except Exception as e:
            logger.error(f"Error fetching emails from {folder}: {e}")
            return {}

    def _decode_header(self, header: str) -> str:
        """Decode an email header.

        Args:
            header: The header to decode

        Returns:
            Decoded header string
        """
        if not header:
            return ""
        
        try:
            decoded_header = ""
            for part, encoding in email.header.decode_header(header):
                if isinstance(part, bytes):
                    if encoding:
                        try:
                            decoded_header += part.decode(encoding)
                        except (LookupError, UnicodeDecodeError):
                            decoded_header += part.decode("utf-8", errors="replace")
                    else:
                        decoded_header += part.decode("utf-8", errors="replace")
                else:
                    decoded_header += part
            return decoded_header
        except Exception as e:
            logger.error(f"Error decoding header: {e}")
            return header

    def _get_email_body(self, message: Message) -> str:
        """Extract the body from an email message.

        Args:
            message: The email message

        Returns:
            The email body as text
        """
        if message.is_multipart():
            # Get the plaintext body from a multipart message
            text_parts = []
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text parts
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            text_parts.append(payload.decode(charset, errors="replace"))
                    except Exception as e:
                        logger.error(f"Error extracting text part: {e}")
            
            return "\n".join(text_parts)
        else:
            # Get the body from a single-part message
            try:
                charset = message.get_content_charset() or "utf-8"
                payload = message.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
                return ""
            except Exception as e:
                logger.error(f"Error extracting message body: {e}")
                return ""

    def categorize_emails(
        self,
        client: IMAPClient,
        email_ids: List[int],
        emails: Dict[int, Dict[str, Any]],
        batch_size: int = 10,
    ) -> Dict[int, Tuple[Dict[str, Any], categorizer.EmailCategory]]:
        """Categorize emails using the OpenAI API.

        Args:
            client: The IMAPClient object
            email_ids: List of message IDs to categorize
            emails: Dictionary mapping message IDs to email data
            batch_size: Number of emails to process in each batch

        Returns:
            Dictionary mapping message IDs to tuples of (email data, category)
        """
        categorized_emails = {}
        
        # Process emails in batches
        for i in range(0, len(email_ids), batch_size):
            batch_ids = email_ids[i:i + batch_size]
            logger.info(f"Categorizing batch of {len(batch_ids)} emails")
            
            for msg_id in batch_ids:
                try:
                    email_data = emails[msg_id]
                    
                    # Extract relevant fields for categorization
                    email_for_categorization = {
                        "subject": email_data["subject"],
                        "from": email_data["from"],
                        "to": email_data["to"],
                        "date": email_data["date"],
                        "body": email_data["body"],
                    }
                    
                    # Categorize the email
                    category = categorizer.categorize_email(email_for_categorization)
                    categorized_emails[msg_id] = (email_data, category)
                    
                    logger.info(f"Categorized email as {category}: {email_data['subject']}")
                except Exception as e:
                    logger.error(f"Error categorizing email: {e}")
            
            # Add a small delay between batches to avoid rate limits
            if i + batch_size < len(email_ids):
                time.sleep(1)
        
        return categorized_emails

    def _ensure_folder_exists(self, client: IMAPClient, folder: str) -> None:
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

    def process_categorized_emails(
        self,
        client: IMAPClient,
        categorized_emails: Dict[int, Tuple[Dict[str, Any], categorizer.EmailCategory]],
        current_folder: str = None,
        account_name: str = None,
    ) -> Dict[categorizer.EmailCategory, int]:
        """Process categorized emails (move to folders, mark as read, etc.).

        Args:
            client: The IMAPClient object
            categorized_emails: Dictionary mapping message IDs to tuples of (email data, category)
            current_folder: The current folder being processed
            account_name: Name of the email account

        Returns:
            Dictionary mapping categories to counts of processed emails
        """
        category_counts = {category: 0 for category in categorizer.EmailCategory}
        
        # Get folder mapping from config
        category_folders = self.options.get("category_folders", {})
        default_folders = {
            "spam": "[Spam]",
            "receipts": "[Receipts]",
            "promotions": "[Promotions]",
            "updates": "[Updates]",
            "inbox": "INBOX",
        }
        
        # Merge with defaults
        for category, folder in default_folders.items():
            if category not in category_folders:
                category_folders[category] = folder
        
        # Process each email
        for msg_id, (email_data, category) in categorized_emails.items():
            try:
                # Mark as processed in local state
                if account_name:
                    self._mark_email_as_processed(account_name, msg_id, email_data)
                
                # Move to appropriate folder if configured
                if self.options.get("move_emails", True):
                    category_name = category.name.lower()
                    target_folder = category_folders.get(category_name)
                    
                    if target_folder and (current_folder is None or target_folder != current_folder):
                        # Ensure target folder exists
                        self._ensure_folder_exists(client, target_folder)
                        
                        # Move the message
                        client.move(msg_id, target_folder)
                        logger.info(f"Moved email to {target_folder}")
                
                category_counts[category] += 1
            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")
        
        return category_counts

    def process_account(self, account: EmailAccount) -> Dict[str, Dict[categorizer.EmailCategory, int]]:
        """Process all unprocessed emails in an account.

        Args:
            account: The EmailAccount to process

        Returns:
            Dictionary mapping folders to category counts
        """
        results = {}
        client = self.connect_to_account(account)
        
        if not client:
            return results
        
        try:
            max_emails = self.options.get("max_emails_per_run", 100)
            
            for folder in account.folders:
                logger.info(f"Processing folder: {folder}")
                
                # Get unprocessed emails
                emails = self.get_unprocessed_emails(client, folder, max_emails, account.name)
                
                if not emails:
                    continue
                
                # Categorize emails
                email_ids = list(emails.keys())
                categorized_emails = self.categorize_emails(
                    client, email_ids, emails, self.options.get("batch_size", 10)
                )
                
                # Process categorized emails
                category_counts = self.process_categorized_emails(
                    client, categorized_emails, folder, account.name
                )
                
                results[folder] = category_counts
            
            # Clean up old entries from the processed state
            self._cleanup_processed_state()
            
            client.logout()
            logger.info(f"Logged out from {account}")
            
            return results
        except Exception as e:
            logger.error(f"Error processing account {account}: {e}")
            try:
                client.logout()
            except:
                pass
            return results

    def process_all_accounts(self) -> Dict[str, Dict[str, Dict[categorizer.EmailCategory, int]]]:
        """Process all accounts.

        Returns:
            Dictionary mapping account names to results
        """
        results = {}
        
        for account in self.accounts:
            logger.info(f"Processing account: {account}")
            results[account.name] = self.process_account(account)
        
        return results

    def start_monitoring(self) -> None:
        """Start continuous monitoring of email accounts."""
        global running
        running = True
        
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            global running
            logger.info("Received shutdown signal, stopping...")
            running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring threads
        threads = []
        for account in self.accounts:
            thread = threading.Thread(
                target=self._monitor_account,
                args=(account,),
                daemon=True
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        while running and any(t.is_alive() for t in threads):
            time.sleep(1)
        
        logger.info("Monitoring stopped")

    def _monitor_account(self, account: EmailAccount) -> None:
        """Monitor an account for new emails.

        Args:
            account: The EmailAccount to monitor
        """
        logger.info(f"Starting monitoring for {account}")
        
        # Initialize reconnection parameters
        max_retry_delay = 300  # 5 minutes
        base_delay = 5  # 5 seconds
        retry_delay = base_delay
        
        while running:
            try:
                client = self.connect_to_account(account)
                
                if not client:
                    logger.error(f"Failed to connect to {account}, retrying in {retry_delay} seconds")
                    time.sleep(retry_delay)
                    # Exponential backoff with maximum delay
                    retry_delay = min(retry_delay * 2, max_retry_delay)
                    continue
                
                # Reset retry delay on successful connection
                retry_delay = base_delay
                
                # Process each folder
                for folder in account.folders:
                    try:
                        logger.info(f"Monitoring folder: {folder}")
                        client.select_folder(folder)
                        
                        # Initial processing of existing emails
                        max_emails = self.options.get("max_emails_per_run", 100)
                        emails = self.get_unprocessed_emails(client, folder, max_emails, account.name)
                        
                        if emails:
                            # Categorize emails
                            email_ids = list(emails.keys())
                            categorized_emails = self.categorize_emails(
                                client, email_ids, emails, self.options.get("batch_size", 10)
                            )
                            
                            # Process categorized emails
                            self.process_categorized_emails(client, categorized_emails, folder, account.name)
                        
                        # Start IDLE mode with shorter timeouts for better error detection
                        logger.info(f"Entering IDLE mode for {folder}")
                        idle_timeout = self.options.get("idle_timeout", 1740)  # Default 29 minutes
                        check_interval = 60  # Check connection every minute
                        
                        while running:
                            try:
                                # Start IDLE with a shorter timeout
                                client.idle()
                                
                                # Wait for new emails or timeout
                                responses = client.idle_check(timeout=check_interval)
                                
                                # End IDLE mode
                                client.idle_done()
                                
                                # Check if we received any new emails
                                if responses:
                                    logger.info(f"Received new emails in {folder}")
                                    
                                    # Process new emails
                                    emails = self.get_unprocessed_emails(client, folder, max_emails, account.name)
                                    
                                    if emails:
                                        # Categorize emails
                                        email_ids = list(emails.keys())
                                        categorized_emails = self.categorize_emails(
                                            client, email_ids, emails, self.options.get("batch_size", 10)
                                        )
                                        
                                        # Process categorized emails
                                        self.process_categorized_emails(client, categorized_emails, folder, account.name)
                                
                                # Check if we should stop
                                if not running:
                                    break
                                
                            except Exception as e:
                                error_msg = str(e).lower()
                                if "socket error: eof" in error_msg or "connection reset" in error_msg:
                                    logger.warning(f"Connection lost for {folder}, will attempt to reconnect")
                                    break
                                else:
                                    logger.error(f"Error in IDLE mode for {folder}: {e}")
                                    break
                    
                    except Exception as e:
                        logger.error(f"Error monitoring folder {folder}: {e}")
                        break
                
                # Clean up old entries from the processed state
                self._cleanup_processed_state()
                
                # Logout
                try:
                    client.logout()
                    logger.info(f"Logged out from {account}")
                except:
                    pass
                
                # Wait before reconnecting
                time.sleep(5)  # Short delay before reconnecting
                
            except Exception as e:
                logger.error(f"Error monitoring account {account}: {e}")
                time.sleep(retry_delay)
                # Exponential backoff with maximum delay
                retry_delay = min(retry_delay * 2, max_retry_delay)
        
        logger.info(f"Stopped monitoring for {account}")


def main(config_path: str, daemon_mode: bool = False) -> None:
    """Main entry point for the IMAP email processor.

    Args:
        config_path: Path to the YAML configuration file
        daemon_mode: Whether to run in continuous monitoring mode
    """
    processor = EmailProcessor(config_path)
    
    if daemon_mode:
        logger.info("Starting continuous email monitoring...")
        processor.start_monitoring()
    else:
        # One-time processing mode
        results = processor.process_all_accounts()
        
        # Print summary
        print("\nEmail Processing Summary:")
        print("=" * 50)
        
        for account_name, account_results in results.items():
            print(f"\nAccount: {account_name}")
            
            for folder, category_counts in account_results.items():
                print(f"  Folder: {folder}")
                
                total = sum(category_counts.values())
                if total == 0:
                    print("    No emails processed")
                    continue
                
                for category, count in category_counts.items():
                    if count > 0:
                        print(f"    {category}: {count} emails")
        
        print("\nProcessing complete!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m emailfilter.imap_client <config_path> [--daemon]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    daemon_mode = "--daemon" in sys.argv
    
    main(config_path, daemon_mode) 