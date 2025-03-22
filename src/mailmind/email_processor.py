"""Email processor for categorizing and processing emails."""

import logging
import os
import signal
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple, Any

from imapclient import IMAPClient

from mailmind import categorizer
from .models import Email, EmailAccount, ProcessingOptions
from .config_manager import ConfigManager
from .sqlite_state_manager import SQLiteStateManager
from .imap_manager import IMAPManager

logger = logging.getLogger(__name__)

# Global flag for controlling the continuous monitoring
running = True

def filter_emails(
    emails: List[Dict[str, str]], 
    filters: Optional[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    """
    Filter emails based on provided criteria.
    
    Args:
        emails: List of email dictionaries with keys like 'subject', 'from', 'body', etc.
        filters: Dictionary of filter criteria (e.g., {'from': 'example.com'})
        
    Returns:
        List of emails that match the filter criteria
    """
    if not filters:
        return emails
    
    filtered_emails = []
    
    for email in emails:
        matches = True
        for key, value in filters.items():
            if key not in email or value not in email[key]:
                matches = False
                break
        
        if matches:
            filtered_emails.append(email)
    
    return filtered_emails

class EmailProcessor:
    """Processes emails from IMAP accounts."""
    
    def __init__(self, config_manager: ConfigManager, imap_manager: IMAPManager = None, state_manager: SQLiteStateManager = None):
        """Initialize the email processor.
        
        Args:
            config_manager: The configuration manager instance
            imap_manager: Optional IMAP manager instance. If None, creates a new one.
            state_manager: Optional state manager instance. If None, creates a new one.
        """
        # Set components
        self.config_manager = config_manager
        self.imap_manager = imap_manager or IMAPManager()
        self.state_manager = state_manager or SQLiteStateManager()
        
        # Memory management settings
        self.max_email_size = 50 * 1024 * 1024  # 50MB max email size
        self.max_batch_memory = 200 * 1024 * 1024  # 200MB max batch memory
        
        # Initialize OpenAI client
        try:
            api_key = self.config_manager.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key not found in configuration")
            categorizer.initialize_openai_client(api_key=api_key)
            logger.debug("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
            raise
    
    def _estimate_email_size(self, email: Email) -> int:
        """Estimate the memory size of an email.
        
        Args:
            email: The email to estimate size for
            
        Returns:
            Estimated size in bytes
        """
        size = 0
        size += len(str(email.message_id))
        size += len(str(email.from_addr or ''))
        size += len(str(email.to_addr or ''))
        size += len(str(email.subject or ''))
        size += len(str(email.date or ''))
        size += len(str(email.body or ''))
        size += sum(len(str(part)) for part in (email.attachments or []))
        return size
    
    def _should_process_email(self, email: Email) -> bool:
        """Check if an email should be processed based on size limits.
        
        Args:
            email: The email to check
            
        Returns:
            True if email should be processed, False otherwise
        """
        size = self._estimate_email_size(email)
        if size > self.max_email_size:
            logger.warning(f"Email {email.message_id} exceeds size limit of {self.max_email_size/1024/1024}MB")
            return False
        return True
    
    def categorize_emails(
        self,
        client: IMAPClient,
        emails: Dict[int, Email],
        account,
        batch_size: int = 10,
    ) -> Dict[int, Tuple[Email, str]]:
        """Categorize emails using the OpenAI API.
        
        Args:
            client: IMAP client
            emails: Dictionary mapping message IDs to Email objects
            account: Email account
            batch_size: Number of emails to process in each batch
            
        Returns:
            Dictionary mapping message IDs to tuples of (Email, category)
        """
        categorized_emails = {}
        msg_ids = list(emails.keys())
        
        # Process in batches
        for i in range(0, len(msg_ids), batch_size):
            batch_ids = msg_ids[i:i+batch_size]
            batch_emails = {}
            batch_size_bytes = 0
            
            # Build batch while respecting memory limits
            for msg_id in batch_ids:
                email = emails[msg_id]
                if not self._should_process_email(email):
                    categorized_emails[msg_id] = (email, "INBOX")  # Default to INBOX
                    continue
                    
                email_size = self._estimate_email_size(email)
                if batch_size_bytes + email_size > self.max_batch_memory:
                    logger.warning(f"Batch memory limit reached at {batch_size_bytes/1024/1024}MB")
                    break
                    
                batch_emails[msg_id] = email
                batch_size_bytes += email_size
            
            if not batch_emails:
                continue
                
            try:
                # Categorize batch
                logger.info(f"Categorizing batch of {len(batch_emails)} emails using {self.config_manager.options.model}")
                results = categorizer.batch_categorize_emails_for_account(
                    list(batch_emails.values()), 
                    account, 
                    len(batch_emails),
                    self.config_manager.options.model
                )
                
                # Process results
                for j, msg_id in enumerate(batch_emails.keys()):
                    if j < len(results):
                        result = results[j]
                        category_name = result.get("category", "INBOX")
                        categorized_emails[msg_id] = (emails[msg_id], category_name)
                    else:
                        categorized_emails[msg_id] = (emails[msg_id], "INBOX")
                        
                # Clear batch from memory
                del batch_emails
                del results
                
            except Exception as e:
                logger.error(f"Error categorizing batch: {e}")
                # Fallback for the entire batch
                for msg_id in batch_emails:
                    categorized_emails[msg_id] = (emails[msg_id], "INBOX")
        
        return categorized_emails
    
    def process_categorized_emails(
        self,
        client: IMAPClient,
        categorized_emails: Dict[int, Tuple[Email, str]],
        account,
        current_folder: str = None,
    ) -> Dict[str, int]:
        """Process categorized emails (move to folders, mark as read, etc.).
        
        Args:
            client: The IMAPClient object
            categorized_emails: Dictionary mapping message IDs to tuples of (Email, category)
            account: The EmailAccount object with category definitions
            current_folder: The current folder being processed
            
        Returns:
            Dictionary mapping categories to counts of processed emails
        """
        # Initialize category counts
        category_counts = {category.name: 0 for category in account.categories}
        
        # Process each email
        for msg_id, (email_obj, category_name) in categorized_emails.items():
            try:
                move_successful = True
                
                # Move to appropriate folder if configured
                if self.config_manager.options.move_emails:
                    target_folder = account.get_folder_for_category(category_name)
                    
                    if target_folder and (current_folder is None or target_folder != current_folder):
                        # Attempt to move the email
                        move_successful = self.imap_manager.move_email(client, msg_id, target_folder)
                        
                        if not move_successful:
                            logger.warning(f"Failed to move email {msg_id} to {target_folder}, skipping database update")
                            continue
                
                # Only mark as processed in the database if the move was successful
                # or if we're not configured to move emails
                if move_successful:
                    # Mark as processed in local state with category information
                    self.state_manager.mark_email_as_processed(account.name, email_obj, category_name)
                    
                    # Update count for this category
                    category_counts[category_name] = category_counts.get(category_name, 0) + 1
                    
                    logger.info(f"Email {msg_id} processed successfully and marked in database")
            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")
        
        return category_counts
    
    def process_account(self, account: EmailAccount) -> Dict[str, Dict[str, int]]:
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
                        logger.debug(f"No unprocessed emails in {folder}")
                        continue
                    
                    # Categorize emails
                    categorized_emails = self.categorize_emails(
                        client,
                        unprocessed_emails,
                        account,
                        self.config_manager.options.batch_size
                    )
                    
                    # Process categorized emails
                    category_counts = self.process_categorized_emails(
                        client,
                        categorized_emails,
                        account,
                        folder
                    )
                    
                    results[folder] = category_counts
                except Exception as e:
                    logger.error(f"Error processing folder {folder}: {e}")
            
            return results
        finally:
            # Clean up
            self.imap_manager.disconnect(account.name)
    
    def process_all_accounts(self) -> Dict[str, Dict[str, Dict[str, int]]]:
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
            logger.debug("Received shutdown signal, stopping...")
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
        reconnect_delay = 60  # Initial delay for reconnection attempts
        max_reconnect_delay = 300  # Maximum delay (5 minutes)
        
        while running:
            try:
                # Connect to account
                client = self.imap_manager.connect(account)
                if not client:
                    logger.error(f"Failed to connect to {account}, retrying in {reconnect_delay} seconds")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                    continue
                
                # Reset reconnect delay on successful connection
                reconnect_delay = 60
                
                try:
                    # Process each folder
                    for folder in account.folders:
                        if not running:
                            break
                        
                        try:
                            # Check connection before processing folder
                            if not self.imap_manager._is_connection_alive(client):
                                logger.warning("Connection lost, reconnecting...")
                                raise ConnectionError("Connection lost")
                            
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
                                # Process unprocessed emails
                                self._process_unprocessed_emails(client, unprocessed_emails, account, folder)
                            
                            # Get initial message count
                            pre_idle_count = len(client.search(['ALL']))
                            logger.debug(f"Message count before IDLE: {pre_idle_count}")
                            
                            # Start IDLE mode with a shorter timeout to check connection more frequently
                            idle_timeout = min(self.config_manager.options.idle_timeout, 300)  # Max 5 minutes
                            try:
                                client.idle()
                                responses = client.idle_check(timeout=idle_timeout)
                            finally:
                                try:
                                    client.idle_done()
                                except Exception as e:
                                    logger.warning(f"Error ending IDLE mode: {e}")
                                    raise ConnectionError("Failed to end IDLE mode")
                            
                            # Log all responses for debugging
                            logger.debug(f"IDLE responses: {responses}")
                            
                            # Check if we received new emails
                            has_new_emails = False
                            for response in responses:
                                if response[1] == b'EXISTS':
                                    has_new_emails = True
                                    logger.debug(f"Detected new email: {response}")
                                    break
                            
                            # Verify connection is still alive
                            if not self.imap_manager._is_connection_alive(client):
                                raise ConnectionError("Connection lost after IDLE")
                            
                            # Double-check by comparing message counts
                            post_idle_messages = client.search(['ALL'])
                            post_idle_count = len(post_idle_messages)
                            logger.debug(f"Message count after IDLE: {post_idle_count}")
                            
                            if post_idle_count > pre_idle_count:
                                logger.debug(f"New messages detected: {post_idle_count - pre_idle_count}")
                                has_new_emails = True
                            
                            if has_new_emails:
                                # Process new emails
                                new_emails = self.imap_manager.get_emails(
                                    client,
                                    folder,
                                    self.config_manager.options.max_emails_per_run
                                )
                                
                                # Filter out already processed emails
                                unprocessed_new = {}
                                for msg_id, email_obj in new_emails.items():
                                    if not self.state_manager.is_email_processed(account.name, email_obj):
                                        unprocessed_new[msg_id] = email_obj
                                
                                if unprocessed_new:
                                    logger.info(f"Processing {len(unprocessed_new)} new emails in {folder}")
                                    self._process_unprocessed_emails(client, unprocessed_new, account, folder)
                            
                            # Small delay between folder checks
                            time.sleep(1)
                            
                        except ConnectionError as e:
                            logger.error(f"Connection error in folder {folder}: {e}")
                            raise  # Re-raise to trigger reconnection
                        except Exception as e:
                            logger.error(f"Error monitoring folder {folder}: {e}")
                            if not self.imap_manager._is_connection_alive(client):
                                raise ConnectionError("Connection lost during folder processing")
                            time.sleep(60)  # Wait before retrying folder
                
                    # Small delay between account checks
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop for {account}: {e}")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            except Exception as e:
                logger.error(f"Error in monitoring loop for {account}: {e}")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


def main(config_path: str, daemon_mode: bool = False) -> None:
    """Main entry point for the email processor.
    
    Args:
        config_path: Path to the configuration file
        daemon_mode: Whether to run in continuous monitoring mode
    """
    from .pre_training import PreTrainingManager  # Import moved here to avoid circular import
    
    try:
        processor = EmailProcessor(config_path)
        
        # Initialize pre-training manager
        pre_training = PreTrainingManager(
            state_manager=processor.state_manager,
            email_processor=processor,
            categorizer=categorizer,
            imap_manager=processor.imap_manager
        )
        
        if daemon_mode:
            # Start pre-training monitoring in a separate thread
            pre_training_thread = threading.Thread(
                target=pre_training.monitor_category_changes,
                kwargs={
                    'check_interval': 600,
                    'lookback_days': processor.config_manager.lookback_days
                },
                daemon=True
            )
            pre_training_thread.start()
            logger.info("Started pre-training monitoring thread")
            
            # Start main email processing
            processor.start_monitoring()
        else:
            # Single run mode
            processor.process_all_accounts()
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1) 