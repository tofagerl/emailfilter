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
from datetime import datetime, timedelta
from email.message import Message
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml
from imapclient import IMAPClient

from emailfilter import categorizer
from .sqlite_state_manager import SQLiteStateManager
from .models import Email as EmailModel

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
        
        # Set up SQLite state manager with default path
        self.state_manager = SQLiteStateManager()
        
        # Load configuration
        self._load_config()
        
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

    def fetch_unprocessed_emails(self, account: EmailAccount, max_emails: int = 100) -> Dict[int, Dict[str, Any]]:
        """Fetch unprocessed emails from an account.
        
        Args:
            account: The email account to fetch from
            max_emails: Maximum number of emails to fetch
            
        Returns:
            Dictionary of email data keyed by message ID
        """
        client = self.connect_to_account(account)
        if not client:
            return {}
        
        email_data = {}
        account_name = account.name
        
        try:
            # Process each folder
            for folder in account.folders:
                if len(email_data) >= max_emails:
                    break
                
                try:
                    # Select the folder
                    client.select_folder(folder)
                    logger.info(f"Selected folder: {folder}")
                    
                    # Search for all emails in the folder
                    messages = client.search("ALL")
                    logger.info(f"Found {len(messages)} messages in {folder}")
                    
                    # Limit the number of messages to process
                    messages = messages[-max_emails:]
                    
                    # Fetch email data
                    for msg_id in messages:
                        if len(email_data) >= max_emails:
                            break
                        
                        try:
                            # Fetch email data
                            raw_data = client.fetch([msg_id], ["ENVELOPE", "RFC822"])
                            if not raw_data or msg_id not in raw_data:
                                continue
                            
                            # Parse email
                            raw_message = raw_data[msg_id][b"RFC822"]
                            message = email.message_from_bytes(raw_message)
                            
                            # Extract email info
                            email_info = self._extract_email_info(message)
                            email_info["folder"] = folder
                            
                            # Create an Email model object for state checking
                            email_model = EmailModel(
                                subject=email_info.get("subject", ""),
                                from_addr=email_info.get("from", ""),
                                to_addr=email_info.get("to", ""),
                                date=email_info.get("date", ""),
                                body=email_info.get("body", ""),
                                raw_message=raw_message,
                                msg_id=msg_id,
                                folder=folder
                            )
                            
                            # Check if this email has been processed before
                            if not self.state_manager.is_email_processed(account_name, email_model):
                                email_data[msg_id] = email_info
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                except Exception as e:
                    logger.error(f"Error processing folder {folder}: {e}")
        finally:
            client.logout()
        
        logger.info(f"Fetched {len(email_data)} unprocessed emails from {account}")
        return email_data

    def process_categorized_emails(
        self, 
        client: IMAPClient, 
        account_name: str, 
        categorized_emails: Dict[str, List[Dict[str, Any]]], 
        category_folders: Dict[str, str],
        move_emails: bool = True
    ) -> Dict[str, int]:
        """Process categorized emails.
        
        Args:
            client: The IMAP client
            account_name: Name of the email account
            categorized_emails: Dictionary of emails categorized by category
            category_folders: Dictionary mapping categories to folder names
            move_emails: Whether to move emails to category folders
            
        Returns:
            Dictionary of counts by category
        """
        results = {category: 0 for category in categorized_emails}
        
        for category, emails in categorized_emails.items():
            for email_data in emails:
                msg_id = email_data.get("msg_id")
                if not msg_id:
                    continue
                
                # Create an Email model object for state management
                email_model = EmailModel(
                    subject=email_data.get("subject", ""),
                    from_addr=email_data.get("from", ""),
                    to_addr=email_data.get("to", ""),
                    date=email_data.get("date", ""),
                    body=email_data.get("body", ""),
                    raw_message=b"",  # We don't need the raw message for marking as processed
                    msg_id=msg_id,
                    folder=email_data.get("folder", "")
                )
                
                # Mark as processed in local state
                if account_name:
                    self.state_manager.mark_email_as_processed(account_name, email_model)
                
                # Move to appropriate folder if configured
                if move_emails and category in category_folders:
                    target_folder = category_folders[category]
                    current_folder = email_data.get("folder", "")
                    
                    # Only move if the target folder is different from the current folder
                    if target_folder and target_folder != current_folder:
                        try:
                            # Select the current folder
                            client.select_folder(current_folder)
                            
                            # Move the email
                            client.copy([msg_id], target_folder)
                            client.delete_messages([msg_id])
                            client.expunge()
                            
                            logger.info(f"Moved email {msg_id} from {current_folder} to {target_folder}")
                        except Exception as e:
                            logger.error(f"Error moving email {msg_id} to {target_folder}: {e}")
                
                results[category] += 1
        
        return results

    def process_emails_once(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Process emails once from all accounts.
        
        Returns:
            Dictionary of results by account and category
        """
        results = {}
        
        for account in self.accounts:
            account_name = account.name
            results[account_name] = {}
            
            # Connect to the account
            client = self.connect_to_account(account)
            if not client:
                continue
            
            try:
                # Fetch unprocessed emails
                max_emails = self.options.get("max_emails_per_run", 100)
                emails = self.fetch_unprocessed_emails(account, max_emails)
                
                if not emails:
                    logger.info(f"No new emails to process for {account}")
                    continue
                
                logger.info(f"Processing {len(emails)} emails for {account}")
                
                # Convert to list format for categorizer
                email_list = []
                for msg_id, email_data in emails.items():
                    email_data["msg_id"] = msg_id
                    email_list.append(email_data)
                
                # Categorize emails
                batch_size = self.options.get("batch_size", 10)
                categorized = categorizer.categorize_and_filter(email_list, batch_size)
                
                # Process categorized emails
                category_folders = self.options.get("category_folders", {})
                move_emails = self.options.get("move_emails", True)
                
                # Reconnect to ensure the connection is fresh
                client = self.connect_to_account(account)
                if not client:
                    continue
                
                results[account_name]["categories"] = self.process_categorized_emails(
                    client, account_name, categorized, category_folders, move_emails
                )
                
                # Clean up old entries from the processed state
                self.state_manager.cleanup_old_entries()
                
                # Logout
                client.logout()
                
            except Exception as e:
                logger.error(f"Error processing emails for {account}: {e}")
                if client:
                    client.logout()
        
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
                        emails = self.fetch_unprocessed_emails(account, max_emails)
                        
                        if emails:
                            # Categorize emails
                            email_ids = list(emails.keys())
                            categorized_emails = self.process_categorized_emails(
                                client, account.name, emails, self.options.get("category_folders", {}), self.options.get("move_emails", True)
                            )
                            
                            # Process categorized emails
                            self.process_categorized_emails(client, account.name, categorized_emails, self.options.get("category_folders", {}), self.options.get("move_emails", True))
                        
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
                                    emails = self.fetch_unprocessed_emails(account, max_emails)
                                    
                                    if emails:
                                        # Categorize emails
                                        email_ids = list(emails.keys())
                                        categorized_emails = self.process_categorized_emails(
                                            client, account.name, emails, self.options.get("category_folders", {}), self.options.get("move_emails", True)
                                        )
                                        
                                        # Process categorized emails
                                        self.process_categorized_emails(client, account.name, categorized_emails, self.options.get("category_folders", {}), self.options.get("move_emails", True))
                                
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
                self.state_manager.cleanup_old_entries()
                
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

    def _extract_email_info(self, message: Message) -> Dict[str, Any]:
        """Extract information from an email message.
        
        Args:
            message: The email message
            
        Returns:
            Dictionary containing email information
        """
        # Extract subject
        subject = ""
        if message["Subject"]:
            try:
                decoded_header = email.header.decode_header(message["Subject"])
                subject_parts = []
                for part, encoding in decoded_header:
                    if isinstance(part, bytes):
                        if encoding:
                            try:
                                subject_parts.append(part.decode(encoding))
                            except (LookupError, UnicodeDecodeError):
                                subject_parts.append(part.decode("utf-8", errors="replace"))
                        else:
                            subject_parts.append(part.decode("utf-8", errors="replace"))
                    else:
                        subject_parts.append(part)
                subject = "".join(subject_parts)
            except Exception as e:
                logger.error(f"Error decoding subject: {e}")
                subject = message["Subject"]
        
        # Extract from address
        from_addr = ""
        if message["From"]:
            try:
                decoded_header = email.header.decode_header(message["From"])
                from_parts = []
                for part, encoding in decoded_header:
                    if isinstance(part, bytes):
                        if encoding:
                            try:
                                from_parts.append(part.decode(encoding))
                            except (LookupError, UnicodeDecodeError):
                                from_parts.append(part.decode("utf-8", errors="replace"))
                        else:
                            from_parts.append(part.decode("utf-8", errors="replace"))
                    else:
                        from_parts.append(part)
                from_addr = "".join(from_parts)
            except Exception as e:
                logger.error(f"Error decoding from address: {e}")
                from_addr = message["From"]
        
        # Extract to address
        to_addr = ""
        if message["To"]:
            try:
                decoded_header = email.header.decode_header(message["To"])
                to_parts = []
                for part, encoding in decoded_header:
                    if isinstance(part, bytes):
                        if encoding:
                            try:
                                to_parts.append(part.decode(encoding))
                            except (LookupError, UnicodeDecodeError):
                                to_parts.append(part.decode("utf-8", errors="replace"))
                        else:
                            to_parts.append(part.decode("utf-8", errors="replace"))
                    else:
                        to_parts.append(part)
                to_addr = "".join(to_parts)
            except Exception as e:
                logger.error(f"Error decoding to address: {e}")
                to_addr = message["To"]
        
        # Extract date
        date = message["Date"] or ""
        
        # Extract body
        body = ""
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
            
            body = "\n".join(text_parts)
        else:
            # Get the body from a single-part message
            try:
                charset = message.get_content_charset() or "utf-8"
                payload = message.get_payload(decode=True)
                if payload:
                    body = payload.decode(charset, errors="replace")
            except Exception as e:
                logger.error(f"Error extracting message body: {e}")
        
        return {
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "date": date,
            "body": body
        }


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
        results = processor.process_emails_once()
        
        # Print summary
        print("\nEmail Processing Summary:")
        print("=" * 50)
        
        for account_name, account_results in results.items():
            print(f"\nAccount: {account_name}")
            
            for category, count in account_results["categories"].items():
                if count > 0:
                    print(f"  Category: {category}")
                    print(f"    Count: {count}")
        
        print("\nProcessing complete!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m emailfilter.imap_client <config_path> [--daemon]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    daemon_mode = "--daemon" in sys.argv
    
    main(config_path, daemon_mode) 