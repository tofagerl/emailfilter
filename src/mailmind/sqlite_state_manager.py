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
            state_dir = os.environ.get('MAILMIND_STATE_DIR', os.path.expanduser("~/.mailmind"))
            db_file_path = os.path.join(state_dir, "processed_emails.db")
            
        self.db_file_path = db_file_path
        self._connection_pool = []
        self._max_connections = 5
        
        # Create directory for database file if it doesn't exist
        os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        logger.debug(f"SQLite state manager initialized with database at {self.db_file_path}")
    
    def _init_db(self) -> None:
        """Initialize the SQLite database and handle migrations."""
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            # Create table for processed emails if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                email_id TEXT NOT NULL,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_name, email_id)
            )
            ''')
            
            # Check if the new columns exist, and add them if they don't
            # This handles migration from older versions of the database
            cursor.execute("PRAGMA table_info(processed_emails)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns if they don't exist
            if 'from_addr' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN from_addr TEXT")
                conn.commit()
                logger.debug("Adding 'from_addr' column to database")
            
            if 'to_addr' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN to_addr TEXT")
                conn.commit()
                logger.debug("Adding 'to_addr' column to database")
            
            if 'subject' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN subject TEXT")
                conn.commit()
                logger.debug("Adding 'subject' column to database")
            
            if 'date' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN date TEXT")
                conn.commit()
                logger.debug("Adding 'date' column to database")
            
            if 'category' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN category TEXT")
                conn.commit()
                logger.debug("Adding 'category' column to database")

            if 'raw_message' not in columns:
                cursor.execute("ALTER TABLE processed_emails ADD COLUMN raw_message BLOB")
                conn.commit()
                logger.debug("Adding 'raw_message' column to database")
            
            # Create index for faster lookups
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_account_email 
            ON processed_emails(account_name, email_id)
            ''')
            
            # Create index for sender searches
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_from_addr
            ON processed_emails(from_addr)
            ''')
            
            # Create index for recipient searches
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_to_addr
            ON processed_emails(to_addr)
            ''')
            
            # Create index for subject searches
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_subject
            ON processed_emails(subject)
            ''')
            
            conn.commit()
            conn.close()
            logger.debug(f"SQLite database initialized at {self.db_file_path}")
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
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection from the pool or create a new one.
        
        Returns:
            A SQLite connection
        """
        if self._connection_pool:
            conn = self._connection_pool.pop()
            if conn is None or not self._is_connection_valid(conn):
                conn = self._create_connection()
            return conn
        return self._create_connection()
    
    def _return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool.
        
        Args:
            conn: The connection to return
        """
        if conn is None:
            return
            
        if len(self._connection_pool) < self._max_connections:
            if self._is_connection_valid(conn):
                self._connection_pool.append(conn)
            else:
                conn.close()
        else:
            conn.close()
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection.
        
        Returns:
            A new SQLite connection
        """
        conn = sqlite3.connect(self.db_file_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _is_connection_valid(self, conn: sqlite3.Connection) -> bool:
        """Check if a connection is still valid.
        
        Args:
            conn: The connection to check
            
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False
    
    def _execute_with_connection(self, operation, *args, **kwargs):
        """Execute a database operation with connection management.
        
        Args:
            operation: Function to execute with the connection
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation
        """
        conn = self._get_connection()
        try:
            result = operation(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._return_connection(conn)
    
    def is_email_processed(self, account_name: str, email: Email) -> bool:
        """Check if an email has been processed.
        
        Args:
            account_name: Name of the email account
            email: The email object
            
        Returns:
            True if the email has been processed, False otherwise
        """
        email_id = self._generate_email_id(account_name, email)
        
        def check_email(conn):
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM processed_emails WHERE account_name = ? AND email_id = ?",
                (account_name, email_id)
            )
            return cursor.fetchone()[0] > 0
            
        return self._execute_with_connection(check_email)
    
    def mark_email_as_processed(self, account_name: str, email: Email, category: str = None) -> None:
        """Mark an email as processed.
        
        Args:
            account_name: Name of the email account
            email: The email object
            category: The category assigned to the email (optional)
        """
        email_id = self._generate_email_id(account_name, email)
        
        def mark_email(conn):
            cursor = conn.cursor()
            
            # Check if this email is already in the database
            cursor.execute(
                "SELECT id FROM processed_emails WHERE account_name = ? AND email_id = ?",
                (account_name, email_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record with new information
                cursor.execute(
                    """
                    UPDATE processed_emails 
                    SET from_addr = ?, to_addr = ?, subject = ?, date = ?, category = ?, raw_message = ?
                    WHERE account_name = ? AND email_id = ?
                    """,
                    (
                        email.from_addr[:255] if email.from_addr else None,
                        email.to_addr[:255] if email.to_addr else None,
                        email.subject[:255] if email.subject else None,
                        email.date,
                        category,
                        email.raw_message,
                        account_name,
                        email_id
                    )
                )
            else:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO processed_emails 
                    (account_name, email_id, from_addr, to_addr, subject, date, category, raw_message) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_name, 
                        email_id, 
                        email.from_addr[:255] if email.from_addr else None,
                        email.to_addr[:255] if email.to_addr else None,
                        email.subject[:255] if email.subject else None,
                        email.date,
                        category,
                        email.raw_message
                    )
                )
            
            logger.debug(
                f"Marked email as processed: {account_name} | "
                f"From: {email.from_addr[:40] if email.from_addr else 'None'} | "
                f"Subject: {email.subject[:40] if email.subject else 'None'} | "
                f"Category: {category or 'None'}"
            )
        
        self._execute_with_connection(mark_email)
    
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
            
            logger.debug(f"Deleted {deleted_count} entries for account {account_name}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting entries for account {account_name}: {e}")
            return 0
    
    def query_processed_emails(
        self, 
        account_name: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        subject: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """Query processed emails by various criteria.
        
        Args:
            account_name: Filter by account name
            from_addr: Filter by sender address (partial match)
            to_addr: Filter by recipient address (partial match)
            subject: Filter by subject (partial match)
            category: Filter by category
            limit: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            List of dictionaries containing email information
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            # Build query
            query = "SELECT * FROM processed_emails WHERE 1=1"
            params = []
            
            if account_name:
                query += " AND account_name = ?"
                params.append(account_name)
            
            if from_addr:
                query += " AND (from_addr LIKE ? OR from_addr IS NULL)"
                params.append(f"%{from_addr}%")
            
            if to_addr:
                query += " AND (to_addr LIKE ? OR to_addr IS NULL)"
                params.append(f"%{to_addr}%")
            
            if subject:
                query += " AND (subject LIKE ? OR subject IS NULL)"
                params.append(f"%{subject}%")
            
            if category:
                query += " AND (category = ? OR category IS NULL)"
                params.append(category)
            
            # Add order by, limit and offset
            query += " ORDER BY processed_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # Execute query
            cursor.execute(query, params)
            
            # Convert rows to dictionaries
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # Ensure all fields have values (not NULL)
                for field in ['from_addr', 'to_addr', 'subject', 'date', 'category']:
                    if result.get(field) is None:
                        result[field] = ""
                # Don't set default for raw_message - keep it as None if not present
                results.append(result)
            
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error querying processed emails: {e}")
            return []
    
    def get_category_stats(self, account_name: Optional[str] = None) -> dict:
        """Get statistics about email categories.
        
        Args:
            account_name: Optional account name to filter by
            
        Returns:
            Dictionary mapping categories to counts
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            if account_name:
                cursor.execute(
                    "SELECT COALESCE(category, 'UNKNOWN') as category, COUNT(*) FROM processed_emails WHERE account_name = ? GROUP BY category",
                    (account_name,)
                )
            else:
                cursor.execute(
                    "SELECT COALESCE(category, 'UNKNOWN') as category, COUNT(*) FROM processed_emails GROUP BY category"
                )
            
            stats = {}
            for row in cursor.fetchall():
                category, count = row
                stats[category] = count
            
            conn.close()
            return stats
        except Exception as e:
            logger.error(f"Error getting category stats: {e}")
            return {} 