"""Manages the state of processed emails using SQLite."""

import os
import hashlib
import logging
import sqlite3
from typing import List, Optional
from datetime import datetime, timedelta

from .models import Email

logger = logging.getLogger(__name__)

class SQLiteStateManager:
    """Manages the state of processed emails using SQLite."""
    
    def __init__(self, db_file_path: str = None):
        """Initialize the state manager.
        
        Args:
            db_file_path: Path to the SQLite database file. If None, uses the default path.
        """
        if db_file_path is None:
            # Use environment variable if set, otherwise use default path
            state_dir = os.environ.get('EMAILFILTER_STATE_DIR', os.path.expanduser("~/.emailfilter"))
            db_file_path = os.path.join(state_dir, "processed_emails.db")
            
        self.db_file_path = db_file_path
        
        # Create directory for database file if it doesn't exist
        os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        logger.info(f"SQLite state manager initialized with database at {self.db_file_path}")
    
    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            # Create table for processed emails
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                email_id TEXT NOT NULL,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_name, email_id)
            )
            ''')
            
            # Create index for faster lookups
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_account_email 
            ON processed_emails(account_name, email_id)
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"SQLite database initialized at {self.db_file_path}")
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {e}")
            raise
    
    def _generate_email_id(self, account_name: str, email: Email) -> str:
        """Generate a unique ID for an email.
        
        Args:
            account_name: Name of the email account
            email: The email object
            
        Returns:
            A unique string ID for the email
        """
        unique_str = f"{account_name}:{email.msg_id}:{email.from_addr}:{email.subject}:{email.date}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def is_email_processed(self, account_name: str, email: Email) -> bool:
        """Check if an email has been processed.
        
        Args:
            account_name: Name of the email account
            email: The email object
            
        Returns:
            True if the email has been processed, False otherwise
        """
        email_id = self._generate_email_id(account_name, email)
        
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) FROM processed_emails WHERE account_name = ? AND email_id = ?",
                (account_name, email_id)
            )
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
        except Exception as e:
            logger.error(f"Error checking if email is processed: {e}")
            return False
    
    def mark_email_as_processed(self, account_name: str, email: Email) -> None:
        """Mark an email as processed.
        
        Args:
            account_name: Name of the email account
            email: The email object
        """
        email_id = self._generate_email_id(account_name, email)
        
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT OR IGNORE INTO processed_emails (account_name, email_id) VALUES (?, ?)",
                (account_name, email_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Marked email as processed: {account_name}:{email_id}")
        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")
    
    def cleanup_old_entries(self, max_age_days: int = 30) -> None:
        """Clean up old entries from the processed state.
        
        Args:
            max_age_days: Maximum age of entries in days
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Delete old entries
            cursor.execute(
                "DELETE FROM processed_emails WHERE processed_date < ?",
                (cutoff_str,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old entries from the database")
        except Exception as e:
            logger.error(f"Error cleaning up old entries: {e}")
    
    def get_processed_count(self, account_name: Optional[str] = None) -> int:
        """Get the count of processed emails.
        
        Args:
            account_name: Optional account name to filter by
            
        Returns:
            The count of processed emails
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            if account_name:
                cursor.execute(
                    "SELECT COUNT(*) FROM processed_emails WHERE account_name = ?",
                    (account_name,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM processed_emails")
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
        except Exception as e:
            logger.error(f"Error getting processed count: {e}")
            return 0
    
    def get_accounts(self) -> List[str]:
        """Get a list of all account names in the database.
        
        Returns:
            A list of account names
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT account_name FROM processed_emails")
            accounts = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return accounts
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return []
    
    def delete_account_entries(self, account_name: str) -> int:
        """Delete all entries for a specific account.
        
        Args:
            account_name: The account name to delete entries for
            
        Returns:
            The number of entries deleted
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM processed_emails WHERE account_name = ?",
                (account_name,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Deleted {deleted_count} entries for account {account_name}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting entries for account {account_name}: {e}")
            return 0 