"""Manages the state of processed emails using SQLite."""

import os
import hashlib
import logging
import sqlite3
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from .models import Email, Category

logger = logging.getLogger(__name__)

class SQLiteStateManager:
    """Manages the state of processed emails using SQLite."""
    
    def __init__(self, db_file_path: str = None):
        """Initialize the state manager.
        
        Args:
            db_file_path: Path to the SQLite database file. If None, uses the default path.
                         Use ':memory:' for an in-memory database.
        """
        if db_file_path is None:
            # Use environment variable if set, otherwise use default path
            state_dir = os.environ.get('MAILMIND_STATE_DIR', os.path.expanduser("~/.mailmind"))
            db_file_path = os.path.join(state_dir, "processed_emails.db")
            
        self.db_file_path = db_file_path
        self._connection_pool = []
        self._max_connections = 5
        self._persistent_connection = None
        
        # Only create directory if not using in-memory database
        if self.db_file_path != ':memory:':
            os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)
        else:
            # For in-memory database, create a persistent connection
            self._persistent_connection = sqlite3.connect(self.db_file_path)
            self._persistent_connection.row_factory = sqlite3.Row
        
        # Initialize database
        self._init_db()
        
        logger.debug(f"SQLite state manager initialized with database at {self.db_file_path}")
    
    def _init_db(self) -> None:
        """Initialize the SQLite database and handle migrations."""
        try:
            if self.db_file_path == ':memory:':
                conn = self._persistent_connection
            else:
                conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            # Create table for processed emails if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                hash_id TEXT NOT NULL,
                message_id TEXT,
                from_addr TEXT,
                to_addr TEXT,
                subject TEXT,
                body TEXT,
                date TEXT,
                folder TEXT,
                category TEXT,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_name, hash_id)
            )
            ''')
            
            # Create table for categories if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                foldername TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, foldername)
            )
            ''')
            
            conn.commit()
            if self.db_file_path != ':memory:':
                conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def add_category(self, name: str, folder_name: str) -> None:
        """Add a new category to the database.
        
        Args:
            name: The name of the category
            folder_name: The IMAP folder name for this category
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO categories (name, folder_name) VALUES (?, ?)",
                (name, folder_name)
            )
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Added category {name} with folder {folder_name}")
            
        except Exception as e:
            logger.error(f"Error adding category: {e}")
            raise
    
    def _generate_email_id(self, account_name: str, email: Email) -> str:
        """Generate a unique ID for an email.
        
        Args:
            account_name: Name of the email account
            email: The email object
            
        Returns:
            A unique hash ID for the email
        """
        # Create a unique string combining account name and email details
        unique_str = f"{account_name}:{email.from_addr}:{email.subject}:{email.date}"
        
        # Generate a hash of the unique string
        hash_id = hashlib.sha256(unique_str.encode()).hexdigest()
        
        return hash_id
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection from the pool or create a new one.
        
        Returns:
            A SQLite connection
        """
        if self.db_file_path == ':memory:':
            return self._persistent_connection
            
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
        if self.db_file_path == ':memory:':
            return
            
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
        hash_id = self._generate_email_id(account_name, email)
        
        def check_email(conn):
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM processed_emails WHERE account_name = ? AND hash_id = ?",
                (account_name, hash_id)
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
        hash_id = self._generate_email_id(account_name, email)
        
        def mark_email(conn):
            cursor = conn.cursor()
            
            # Check if this email is already in the database
            cursor.execute(
                "SELECT id FROM processed_emails WHERE account_name = ? AND hash_id = ?",
                (account_name, hash_id)
            )
            result = cursor.fetchone()
            
            if result:
                # Update existing record
                cursor.execute(
                    """
                    UPDATE processed_emails 
                    SET category = ?, folder = ?, processed_date = CURRENT_TIMESTAMP
                    WHERE account_name = ? AND hash_id = ?
                    """,
                    (category, email.folder, account_name, hash_id)
                )
            else:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO processed_emails (
                        account_name, hash_id, message_id, from_addr, to_addr, subject, 
                        body, date, folder, category
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_name, hash_id, email.message_id, email.from_addr, email.to_addr,
                        email.subject, email.body, email.date.isoformat(), email.folder, category
                    )
                )
            
            logger.debug(f"Marked email {hash_id} as processed with category {category}")
        
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

    def get_all_categories(self) -> List[dict]:
        """Get all categories from the database.
        
        Returns:
            List of dictionaries containing category information
        """
        try:
            conn = sqlite3.connect(self.db_file_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM categories ORDER BY name")
            
            # Convert rows to dictionaries
            categories = []
            for row in cursor.fetchall():
                categories.append(dict(row))
            
            conn.close()
            return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def get_all_emails_with_categories(self) -> List[Tuple[Email, Category]]:
        """Get all processed emails with their categories.
        
        Returns:
            List of tuples containing (Email, Category) pairs
        """
        def get_emails(conn):
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    pe.account_name, pe.hash_id, pe.message_id, pe.from_addr, pe.to_addr, 
                    pe.subject, pe.body, pe.date, pe.folder, pe.category,
                    c.name, c.description, c.foldername
                FROM processed_emails pe
                LEFT JOIN categories c ON pe.category = c.name
                WHERE pe.category IS NOT NULL
            """)
            
            results = []
            for row in cursor.fetchall():
                email = Email(
                    from_addr=row[3],
                    to_addr=row[4],
                    subject=row[5],
                    body=row[6],
                    date=datetime.fromisoformat(row[7]),
                    folder=row[8] or "INBOX",
                    message_id=row[2]
                )
                
                category = Category(
                    name=row[10],
                    description=row[11],
                    foldername=row[12] or "INBOX"
                ) if row[10] else None
                
                results.append((email, category))
            
            return results
        
        return self._execute_with_connection(get_emails) 