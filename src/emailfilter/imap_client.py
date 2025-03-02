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
from email.message import Message
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml
from imapclient import IMAPClient, SEEN

from emailfilter import categorizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
            imap_server: The IMAP server address
            imap_port: The IMAP server port (default: 993)
            ssl: Whether to use SSL (default: True)
            folders: List of folders to process (default: ["INBOX"])
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
        """Initialize the email processor with a configuration file.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.accounts = self._parse_accounts()
        self.options = self.config.get("options", {})
        self.idle_timeout = self.options.get("idle_timeout", 60 * 29)  # Default: 29 minutes
        self.reconnect_delay = self.options.get("reconnect_delay", 5)  # Default: 5 seconds
        self.threads = []
        
        # Set OpenAI API key if provided in config
        if "openai_api_key" in self.config:
            os.environ["OPENAI_API_KEY"] = self.config["openai_api_key"]

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from the YAML file.

        Returns:
            Dict containing the configuration
        """
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return {}

    def _parse_accounts(self) -> List[EmailAccount]:
        """Parse the accounts from the configuration.

        Returns:
            List of EmailAccount objects
        """
        accounts = []
        for account_config in self.config.get("accounts", []):
            try:
                account = EmailAccount(
                    name=account_config["name"],
                    email_address=account_config["email"],
                    password=account_config["password"],
                    imap_server=account_config["imap_server"],
                    imap_port=account_config.get("imap_port", 993),
                    ssl=account_config.get("ssl", True),
                    folders=account_config.get("folders", ["INBOX"]),
                )
                accounts.append(account)
            except KeyError as e:
                logger.error(f"Missing required field in account configuration: {e}")
        return accounts

    def connect_to_account(self, account: EmailAccount) -> Optional[IMAPClient]:
        """Connect to an email account via IMAP.

        Args:
            account: The EmailAccount to connect to

        Returns:
            IMAPClient object if successful, None otherwise
        """
        try:
            client = IMAPClient(account.imap_server, port=account.imap_port, use_uid=True)
            client.login(account.email_address, account.password)
            logger.info(f"Connected to {account}")
            return client
        except Exception as e:
            logger.error(f"Error connecting to {account}: {e}")
            return None

    def get_unprocessed_emails(
        self, client: IMAPClient, folder: str, max_emails: int = 100
    ) -> Dict[int, Dict[str, Any]]:
        """Get unprocessed emails from a folder.

        Args:
            client: The IMAPClient object
            folder: The folder to fetch emails from
            max_emails: Maximum number of emails to fetch

        Returns:
            Dictionary mapping message IDs to email data
        """
        try:
            client.select_folder(folder)
            
            # Search for emails that don't have the processed flag
            if self.options.get("add_processed_flag", True):
                # Use NOT FLAGGED instead of NOT KEYWORD \Flagged
                messages = client.search(["NOT", "FLAGGED"])
            else:
                messages = client.search(["ALL"])
            
            # Limit the number of messages
            messages = messages[:max_emails]
            
            if not messages:
                logger.info(f"No unprocessed emails found in {folder}")
                return {}
            
            logger.info(f"Found {len(messages)} unprocessed emails in {folder}")
            
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
                    
                    email_data[msg_id] = {
                        "subject": subject,
                        "from": from_addr,
                        "to": to_addr,
                        "date": date,
                        "body": body,
                        "raw_message": raw_message,
                    }
                except Exception as e:
                    logger.error(f"Error processing message {msg_id}: {e}")
            
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
        decoded_header = ""
        try:
            decoded_parts = email.header.decode_header(header)
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_part = part.decode(encoding or "utf-8", errors="replace")
                else:
                    decoded_part = part
                decoded_header += decoded_part
        except Exception:
            decoded_header = header
        return decoded_header

    def _get_email_body(self, msg: Message) -> str:
        """Extract the body text from an email message.

        Args:
            msg: The email message

        Returns:
            The email body as text
        """
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text content
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode(charset, errors="replace")
                    except Exception as e:
                        logger.error(f"Error extracting text content: {e}")
        else:
            # Not multipart - get the payload directly
            try:
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    body += payload.decode(charset, errors="replace")
            except Exception as e:
                logger.error(f"Error extracting message payload: {e}")
        
        # Clean up the body text
        body = re.sub(r"\r\n", "\n", body)
        body = re.sub(r"\n{3,}", "\n\n", body)
        
        return body

    def categorize_emails(
        self, emails: Dict[int, Dict[str, Any]]
    ) -> Dict[int, Tuple[Dict[str, Any], categorizer.EmailCategory]]:
        """Categorize emails using the OpenAI API.

        Args:
            emails: Dictionary mapping message IDs to email data

        Returns:
            Dictionary mapping message IDs to tuples of (email data, category)
        """
        categorized_emails = {}
        batch_size = self.options.get("batch_size", 10)
        
        # Process emails in batches
        email_ids = list(emails.keys())
        for i in range(0, len(email_ids), batch_size):
            batch_ids = email_ids[i:i+batch_size]
            logger.info(f"Categorizing batch of {len(batch_ids)} emails")
            
            for msg_id in batch_ids:
                email_data = emails[msg_id]
                try:
                    category = categorizer.categorize_email(email_data)
                    categorized_emails[msg_id] = (email_data, category)
                    logger.info(f"Categorized email '{email_data['subject']}' as {category}")
                except Exception as e:
                    logger.error(f"Error categorizing email: {e}")
            
            # Add a small delay between batches to avoid rate limits
            if i + batch_size < len(email_ids):
                time.sleep(1)
        
        return categorized_emails

    def process_categorized_emails(
        self,
        client: IMAPClient,
        categorized_emails: Dict[int, Tuple[Dict[str, Any], categorizer.EmailCategory]],
        current_folder: str = None,
    ) -> Dict[categorizer.EmailCategory, int]:
        """Process categorized emails (move to folders, mark as read, etc.).

        Args:
            client: The IMAPClient object
            categorized_emails: Dictionary mapping message IDs to tuples of (email data, category)
            current_folder: The current folder being processed

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
                # Mark as processed
                if self.options.get("add_processed_flag", True):
                    client.add_flags(msg_id, "\\Flagged")
                
                # Mark as read if configured
                if self.options.get("mark_as_read", False):
                    client.add_flags(msg_id, SEEN)
                
                # Move to appropriate folder if configured
                if self.options.get("move_emails", True):
                    category_name = category.name.lower()
                    target_folder = category_folders.get(category_name)
                    
                    if target_folder and (current_folder is None or target_folder != current_folder):
                        # Check if folder exists, create if needed
                        folders = [f.decode() if isinstance(f, bytes) else f for f in client.list_folders()]
                        folder_names = [f[2] for f in folders]
                        
                        if target_folder not in folder_names:
                            logger.info(f"Creating folder: {target_folder}")
                            client.create_folder(target_folder)
                        
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
                emails = self.get_unprocessed_emails(client, folder, max_emails)
                
                if not emails:
                    results[folder] = {category: 0 for category in categorizer.EmailCategory}
                    continue
                
                # Categorize emails
                categorized_emails = self.categorize_emails(emails)
                
                # Process categorized emails
                category_counts = self.process_categorized_emails(client, categorized_emails, folder)
                
                results[folder] = category_counts
        except Exception as e:
            logger.error(f"Error processing account {account}: {e}")
        finally:
            try:
                client.logout()
                logger.info(f"Logged out from {account}")
            except Exception:
                pass
        
        return results

    def process_all_accounts(self) -> Dict[str, Dict[str, Dict[categorizer.EmailCategory, int]]]:
        """Process all accounts in the configuration.

        Returns:
            Dictionary mapping account names to results
        """
        results = {}
        
        for account in self.accounts:
            logger.info(f"Processing account: {account}")
            account_results = self.process_account(account)
            results[account.name] = account_results
        
        return results
        
    def monitor_folder(self, account: EmailAccount, folder: str) -> None:
        """Monitor a folder for new emails using IMAP IDLE.
        
        Args:
            account: The EmailAccount to monitor
            folder: The folder to monitor
        """
        global running
        
        logger.info(f"Starting monitoring for {account.name} - {folder}")
        
        while running:
            client = None
            try:
                # Connect to the account
                client = self.connect_to_account(account)
                if not client:
                    logger.error(f"Failed to connect to {account.name}, retrying in {self.reconnect_delay} seconds")
                    time.sleep(self.reconnect_delay)
                    continue
                
                # Select the folder
                client.select_folder(folder)
                logger.info(f"Monitoring {folder} in {account.name}")
                
                # Process any existing unprocessed emails
                max_emails = self.options.get("max_emails_per_run", 100)
                emails = self.get_unprocessed_emails(client, folder, max_emails)
                
                if emails:
                    categorized_emails = self.categorize_emails(emails)
                    category_counts = self.process_categorized_emails(client, categorized_emails, folder)
                    
                    # Log the results
                    total = sum(category_counts.values())
                    if total > 0:
                        logger.info(f"Processed {total} existing emails in {folder}")
                        for category, count in category_counts.items():
                            if count > 0:
                                logger.info(f"  {category}: {count} emails")
                
                # Start IDLE mode
                while running:
                    # Use IDLE command to wait for server notifications
                    client.idle()
                    
                    # Wait for new emails or timeout
                    responses = client.idle_check(timeout=self.idle_timeout)
                    
                    # End IDLE mode
                    client.idle_done()
                    
                    # Check if we received any new messages
                    new_emails = False
                    for response in responses:
                        if response[1] == b'EXISTS':
                            new_emails = True
                            break
                    
                    if new_emails:
                        logger.info(f"New emails detected in {folder} for {account.name}")
                        
                        # Process new emails
                        emails = self.get_unprocessed_emails(client, folder, max_emails)
                        
                        if emails:
                            categorized_emails = self.categorize_emails(emails)
                            category_counts = self.process_categorized_emails(client, categorized_emails, folder)
                            
                            # Log the results
                            total = sum(category_counts.values())
                            if total > 0:
                                logger.info(f"Processed {total} new emails in {folder}")
                                for category, count in category_counts.items():
                                    if count > 0:
                                        logger.info(f"  {category}: {count} emails")
                    else:
                        logger.debug(f"IDLE timeout for {account.name} - {folder}, refreshing connection")
                
            except Exception as e:
                logger.error(f"Error in monitor_folder for {account.name} - {folder}: {e}")
                
                # If we have a client, try to logout
                if client:
                    try:
                        client.logout()
                    except:
                        pass
                
                # Wait before reconnecting
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)
    
    def start_monitoring(self) -> None:
        """Start monitoring all accounts and folders for new emails."""
        global running
        running = True
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            global running
            logger.info("Shutdown signal received, stopping monitoring...")
            running = False
            
            # Wait for all threads to finish
            for thread in self.threads:
                if thread.is_alive():
                    thread.join()
            
            logger.info("All monitoring threads stopped")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start a thread for each account and folder
        for account in self.accounts:
            for folder in account.folders:
                thread = threading.Thread(
                    target=self.monitor_folder,
                    args=(account, folder),
                    name=f"Monitor-{account.name}-{folder}"
                )
                thread.daemon = True
                thread.start()
                self.threads.append(thread)
                logger.info(f"Started monitoring thread for {account.name} - {folder}")
        
        # Keep the main thread alive
        try:
            while running and any(thread.is_alive() for thread in self.threads):
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping monitoring...")
            running = False
        
        # Wait for all threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join()
        
        logger.info("All monitoring threads stopped")


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