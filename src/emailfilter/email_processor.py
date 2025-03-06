"""Email processor for categorizing and processing emails."""

import logging
import os
import signal
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple, Any

from imapclient import IMAPClient

from emailfilter import categorizer
from .models import Email, EmailAccount, ProcessingOptions
from .config_manager import ConfigManager
from .sqlite_state_manager import SQLiteStateManager
from .imap_manager import IMAPManager

logger = logging.getLogger(__name__)

# Global flag for controlling the continuous monitoring
running = True

class EmailProcessor:
    """Processes emails from IMAP accounts."""
    
    def __init__(self, config_path: str):
        """Initialize the email processor.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        # Initialize components
        self.config_manager = ConfigManager(config_path)
        
        # Set up state manager - use SQLite with default path
        self.state_manager = SQLiteStateManager()
        
        # Set up IMAP manager
        self.imap_manager = IMAPManager()
        
        # Set OpenAI API key
        try:
            categorizer.set_api_key(self.config_manager.openai_api_key)
            logger.info("OpenAI API key loaded successfully")
        except Exception as e:
            logger.error(f"Error loading OpenAI API key: {e}")
            raise
    
    def categorize_emails(
        self,
        client: IMAPClient,
        emails: Dict[int, Email],
        batch_size: int = 10,
    ) -> Dict[int, Tuple[Email, categorizer.EmailCategory]]:
        """Categorize emails using the OpenAI API.
        
        Args:
            client: The IMAPClient object
            emails: Dictionary mapping message IDs to Email objects
            batch_size: Number of emails to categorize in each batch
            
        Returns:
            Dictionary mapping message IDs to tuples of (Email, category)
        """
        if not emails:
            return {}
        
        # Convert Email objects to dictionaries for categorizer
        email_dicts = {
            msg_id: {
                "subject": email.subject,
                "from": email.from_addr,
                "to": email.to_addr,
                "date": email.date,
                "body": email.body
            } for msg_id, email in emails.items()
        }
        
        # Prepare batches
        msg_ids = list(emails.keys())
        categorized_emails = {}
        
        # Process in batches
        for i in range(0, len(msg_ids), batch_size):
            batch_ids = msg_ids[i:i+batch_size]
            batch_emails = [email_dicts[msg_id] for msg_id in batch_ids]
            
            try:
                # Categorize batch
                logger.info(f"Categorizing batch of {len(batch_emails)} emails")
                results = categorizer.batch_categorize_emails(batch_emails, batch_size)
                
                # Process results
                for j, msg_id in enumerate(batch_ids):
                    if j < len(results):
                        result = results[j]
                        # Convert string category to enum
                        category_str = result.get("category", "inbox").upper()
                        try:
                            category = categorizer.EmailCategory[category_str]
                        except KeyError:
                            logger.warning(f"Invalid category '{category_str}', defaulting to INBOX")
                            category = categorizer.EmailCategory.INBOX
                        categorized_emails[msg_id] = (emails[msg_id], category)
                    else:
                        # Fallback if result is missing
                        categorized_emails[msg_id] = (emails[msg_id], categorizer.EmailCategory.INBOX)
            except Exception as e:
                logger.error(f"Error categorizing batch: {e}")
                # Fallback for the entire batch
                for msg_id in batch_ids:
                    categorized_emails[msg_id] = (emails[msg_id], categorizer.EmailCategory.INBOX)
        
        return categorized_emails
    
    def process_categorized_emails(
        self,
        client: IMAPClient,
        categorized_emails: Dict[int, Tuple[Email, categorizer.EmailCategory]],
        current_folder: str = None,
        account_name: str = None,
    ) -> Dict[categorizer.EmailCategory, int]:
        """Process categorized emails (move to folders, mark as read, etc.).
        
        Args:
            client: The IMAPClient object
            categorized_emails: Dictionary mapping message IDs to tuples of (Email, category)
            current_folder: The current folder being processed
            account_name: Name of the email account
            
        Returns:
            Dictionary mapping categories to counts of processed emails
        """
        category_counts = {category: 0 for category in categorizer.EmailCategory}
        
        # Get folder mapping from config
        category_folders = self.config_manager.options.category_folders
        
        # Process each email
        for msg_id, (email_obj, category) in categorized_emails.items():
            try:
                # Mark as processed in local state
                if account_name:
                    self.state_manager.mark_email_as_processed(account_name, email_obj)
                
                # Move to appropriate folder if configured
                if self.config_manager.options.move_emails:
                    category_name = category.name.lower()
                    target_folder = category_folders.get(category_name)
                    
                    if target_folder and (current_folder is None or target_folder != current_folder):
                        self.imap_manager.move_email(client, msg_id, target_folder)
                
                category_counts[category] += 1
            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")
        
        return category_counts
    
    def process_account(self, account: EmailAccount) -> Dict[str, Dict[categorizer.EmailCategory, int]]:
        """Process emails for a single account.
        
        Args:
            account: The email account to process
            
        Returns:
            Dictionary mapping folders to dictionaries mapping categories to counts
        """
        results = {}
        
        # Connect to account
        client = self.imap_manager.connect(account)
        if not client:
            logger.error(f"Failed to connect to {account}")
            return results
        
        try:
            # Process each folder
            for folder in account.folders:
                try:
                    # Get all emails
                    emails = self.imap_manager.get_emails(
                        client, 
                        folder, 
                        self.config_manager.options.max_emails_per_run
                    )
                    
                    # Filter out already processed emails
                    unprocessed_emails = {}
                    for msg_id, email_obj in emails.items():
                        if not self.state_manager.is_email_processed(account.name, email_obj):
                            unprocessed_emails[msg_id] = email_obj
                    
                    if not unprocessed_emails:
                        logger.info(f"No unprocessed emails in {folder}")
                        continue
                    
                    # Categorize emails
                    categorized_emails = self.categorize_emails(
                        client,
                        unprocessed_emails,
                        self.config_manager.options.batch_size
                    )
                    
                    # Process categorized emails
                    category_counts = self.process_categorized_emails(
                        client,
                        categorized_emails,
                        folder,
                        account.name
                    )
                    
                    results[folder] = category_counts
                except Exception as e:
                    logger.error(f"Error processing folder {folder}: {e}")
            
            return results
        finally:
            # Clean up
            self.imap_manager.disconnect(account.name)
    
    def process_all_accounts(self) -> Dict[str, Dict[str, Dict[categorizer.EmailCategory, int]]]:
        """Process emails for all accounts.
        
        Returns:
            Dictionary mapping account names to dictionaries mapping folders to dictionaries mapping categories to counts
        """
        results = {}
        
        for account in self.config_manager.accounts:
            try:
                account_results = self.process_account(account)
                results[account.name] = account_results
            except Exception as e:
                logger.error(f"Error processing account {account}: {e}")
        
        # Clean up old entries
        self.state_manager.cleanup_old_entries()
        
        return results
    
    def start_monitoring(self) -> None:
        """Start monitoring email accounts continuously."""
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
        for account in self.config_manager.accounts:
            thread = threading.Thread(
                target=self._monitor_account,
                args=(account,),
                daemon=True
            )
            thread.start()
            threads.append(thread)
        
        # Wait for threads to complete
        try:
            while running and any(t.is_alive() for t in threads):
                time.sleep(1)
        finally:
            running = False
            for thread in threads:
                thread.join(timeout=5)
    
    def _monitor_account(self, account: EmailAccount) -> None:
        """Monitor an email account continuously.
        
        Args:
            account: The email account to monitor
        """
        global running
        
        while running:
            try:
                # Connect to account
                client = self.imap_manager.connect(account)
                if not client:
                    logger.error(f"Failed to connect to {account}, retrying in 60 seconds")
                    time.sleep(60)
                    continue
                
                try:
                    # Process each folder
                    for folder in account.folders:
                        if not running:
                            break
                        
                        try:
                            # Select folder
                            client.select_folder(folder)
                            
                            # First, process all existing emails in the folder
                            logger.info(f"Processing existing emails in {folder}")
                            emails = self.imap_manager.get_emails(
                                client, 
                                folder, 
                                self.config_manager.options.max_emails_per_run
                            )
                            
                            # Filter out already processed emails
                            unprocessed_emails = {}
                            for msg_id, email_obj in emails.items():
                                if not self.state_manager.is_email_processed(account.name, email_obj):
                                    unprocessed_emails[msg_id] = email_obj
                            
                            if unprocessed_emails:
                                logger.info(f"Found {len(unprocessed_emails)} unprocessed emails in {folder}")
                                # Categorize emails
                                categorized_emails = self.categorize_emails(
                                    client,
                                    unprocessed_emails,
                                    self.config_manager.options.batch_size
                                )
                                
                                # Process categorized emails
                                self.process_categorized_emails(
                                    client,
                                    categorized_emails,
                                    folder,
                                    account.name
                                )
                            else:
                                logger.info(f"No unprocessed emails found in {folder}")
                            
                            # Now enter IDLE mode to wait for new emails
                            logger.info(f"Waiting for new emails in {folder}")
                            client.idle()
                            
                            # Wait for new emails or timeout
                            responses = client.idle_check(timeout=self.config_manager.options.idle_timeout)
                            client.idle_done()
                            
                            # Check if we received new emails
                            has_new_emails = False
                            for response in responses:
                                if response[1] == b'EXISTS':
                                    has_new_emails = True
                                    break
                            
                            if has_new_emails:
                                # Get new emails
                                emails = self.imap_manager.get_emails(
                                    client, 
                                    folder, 
                                    self.config_manager.options.max_emails_per_run
                                )
                                
                                # Filter out already processed emails
                                unprocessed_emails = {}
                                for msg_id, email_obj in emails.items():
                                    if not self.state_manager.is_email_processed(account.name, email_obj):
                                        unprocessed_emails[msg_id] = email_obj
                                
                                if unprocessed_emails:
                                    # Categorize emails
                                    categorized_emails = self.categorize_emails(
                                        client,
                                        unprocessed_emails,
                                        self.config_manager.options.batch_size
                                    )
                                    
                                    # Process categorized emails
                                    self.process_categorized_emails(
                                        client,
                                        categorized_emails,
                                        folder,
                                        account.name
                                    )
                        except Exception as e:
                            logger.error(f"Error monitoring folder {folder}: {e}")
                            time.sleep(60)  # Wait before retrying
                finally:
                    # Disconnect
                    self.imap_manager.disconnect(account.name)
            except Exception as e:
                logger.error(f"Error in monitoring loop for {account}: {e}")
                time.sleep(60)  # Wait before retrying


def main(config_path: str, daemon_mode: bool = False) -> None:
    """Main entry point for the email processor.
    
    Args:
        config_path: Path to the YAML configuration file
        daemon_mode: Whether to run in daemon mode (continuous monitoring)
    """
    try:
        processor = EmailProcessor(config_path)
        
        if daemon_mode:
            logger.info("Starting in daemon mode")
            processor.start_monitoring()
        else:
            logger.info("Processing emails (one-time run)")
            results = processor.process_all_accounts()
            
            # Print results
            for account_name, account_results in results.items():
                print(f"Results for {account_name}:")
                for folder, category_counts in account_results.items():
                    print(f"  Folder: {folder}")
                    for category, count in category_counts.items():
                        if count > 0:
                            print(f"    {category}: {count}")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1) 