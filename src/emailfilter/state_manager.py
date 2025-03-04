"""Manages the state of processed emails."""

import json
import os
import hashlib
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .models import Email

logger = logging.getLogger(__name__)

class EmailStateManager:
    """Manages the state of processed emails."""
    
    def __init__(self, state_file_path: str):
        """Initialize the state manager.
        
        Args:
            state_file_path: Path to the JSON file storing processed email state
        """
        self.state_file_path = state_file_path
        self.processed_state: Dict[str, List[str]] = {}
        
        # Create directory for state file if it doesn't exist
        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        
        # Load existing state
        self._load_state()
    
    def _load_state(self) -> None:
        """Load the processed state from file."""
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
    
    def _save_state(self) -> None:
        """Save the processed state to file."""
        try:
            with open(self.state_file_path, "w") as f:
                json.dump(self.processed_state, f)
            logger.info(f"Saved processed state with {sum(len(ids) for ids in self.processed_state.values())} emails")
        except Exception as e:
            logger.error(f"Error saving processed state: {e}")
    
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
        return account_name in self.processed_state and email_id in self.processed_state[account_name]
    
    def mark_email_as_processed(self, account_name: str, email: Email) -> None:
        """Mark an email as processed.
        
        Args:
            account_name: Name of the email account
            email: The email object
        """
        email_id = self._generate_email_id(account_name, email)
        
        # Initialize account in state if not exists
        if account_name not in self.processed_state:
            self.processed_state[account_name] = []
            
        # Add email ID to processed state
        self.processed_state[account_name].append(email_id)
        
        # Save state after each update
        self._save_state()
    
    def cleanup_old_entries(self, max_age_days: int = 30) -> None:
        """Clean up old entries from the processed state.
        
        Args:
            max_age_days: Maximum age of entries in days
        """
        # For now, just limit the size of each account's list
        max_entries = 10000  # Adjust as needed
        for account_name in self.processed_state:
            if len(self.processed_state[account_name]) > max_entries:
                # Keep only the most recent entries
                self.processed_state[account_name] = self.processed_state[account_name][-max_entries:]
        
        # Save the cleaned up state
        self._save_state() 