"""SQLite-based state manager for tracking processed emails."""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .inference.models import Email

logger = logging.getLogger(__name__)

class SQLiteStateManager:
    """Manages local state using SQLite database."""
    
    def __init__(self, db_file_path: Optional[str] = None):
        """Initialize the state manager.
        
        Args:
            db_file_path: Path to SQLite database file
        """
        if db_file_path is None:
            # Use environment variable if set, otherwise use default path
            state_dir = os.environ.get('MAILMIND_STATE_DIR', os.path.expanduser("~/.mailmind"))
            db_file_path = os.path.join(state_dir, "processed_emails.db")
            
            # Create state directory if it doesn't exist
            os.makedirs(os.path.dirname(db_file_path), exist_ok=True)
        
        self.db_file_path = db_file_path
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_file_path) as conn:
            cursor = conn.cursor()
            
            # Create table for processed emails
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for message_id
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON processed_emails(message_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_date ON processed_emails(processed_date)")
            
            conn.commit()
    
    def is_processed(self, message_id: str) -> bool:
        """Check if an email has been processed.
        
        Args:
            message_id: Message ID to check
            
        Returns:
            True if the email has been processed, False otherwise
        """
        with sqlite3.connect(self.db_file_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM processed_emails WHERE message_id = ?",
                (message_id,)
            )
            
            return cursor.fetchone() is not None
    
    def mark_processed(self, message_id: str) -> None:
        """Mark an email as processed.
        
        Args:
            message_id: Message ID to mark as processed
        """
        with sqlite3.connect(self.db_file_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO processed_emails (message_id)
                VALUES (?)
            """, (message_id,))
            
            conn.commit()
    
    def cleanup_old_entries(self, max_age_days: int = 30) -> None:
        """Clean up old entries from the database.
        
        Args:
            max_age_days: Maximum age of entries to keep (in days)
        """
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        with sqlite3.connect(self.db_file_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM processed_emails WHERE processed_date < ?",
                (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
            )
            
            conn.commit()
    
    def clear(self) -> None:
        """Clear all entries from the database."""
        with sqlite3.connect(self.db_file_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processed_emails")
            conn.commit()