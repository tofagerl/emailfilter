from typing import List, Dict, Optional
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import time
from datetime import datetime, timedelta

from .models import Email, Category
from .sqlite_state_manager import SQLiteStateManager
from .email_processor import EmailProcessor
from .categorizer import Categorizer
from .imap_manager import IMAPManager

logger = logging.getLogger(__name__)

class PreTrainingManager:
    """Manages pre-training data preparation and analysis for the email categorization system."""
    
    def __init__(
        self,
        state_manager: SQLiteStateManager,
        email_processor: EmailProcessor,
        categorizer: Categorizer,
        imap_manager: IMAPManager
    ):
        self.state_manager = state_manager
        self.email_processor = email_processor
        self.categorizer = categorizer
        self.imap_manager = imap_manager
        
    def monitor_category_changes(
        self,
        check_interval: int = 600,  # 10 minutes in seconds
        lookback_days: int = 7  # How far back to check emails
    ) -> None:
        """
        Monitor IMAP folders for category changes and update the database accordingly.
        Runs continuously with the specified check interval.
        
        Args:
            check_interval: Time between checks in seconds (default: 600)
            lookback_days: Number of days to look back for email changes (default: 7)
        """
        while True:
            try:
                logger.info("Starting category change check")
                self._check_category_changes(lookback_days)
                logger.info(f"Category check complete. Sleeping for {check_interval} seconds")
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error during category monitoring: {e}")
                time.sleep(check_interval)  # Still sleep on error to prevent rapid retries
                
    def _check_category_changes(self, lookback_days: int) -> None:
        """
        Check for category changes in IMAP folders and update database.
        
        Args:
            lookback_days: Number of days to look back for email changes
        """
        # Get all category folders from IMAP
        categories = self.state_manager.get_all_categories()
        since_date = datetime.now() - timedelta(days=lookback_days)
        
        for category in categories:
            # Get emails from this category's folder
            folder_emails = self.imap_manager.fetch_emails_from_folder(
                category.folder_name,
                since=since_date
            )
            
            for msg_id, email_data in folder_emails.items():
                # Check if this email exists in our database
                existing_email = self.state_manager.get_email_by_message_id(msg_id)
                
                if existing_email:
                    # Email exists - check if category changed
                    if existing_email.category_id != category.id:
                        logger.info(
                            f"Category change detected for email {msg_id}: "
                            f"from {existing_email.category.name if existing_email.category else 'None'} "
                            f"to {category.name}"
                        )
                        # Update category in database
                        self.state_manager.update_email_category(
                            existing_email.id,
                            category.id
                        )
                else:
                    # Email doesn't exist - add it to database
                    logger.info(f"New email {msg_id} found in category {category.name}")
                    processed_content = self.email_processor.process_email_content(
                        email_data.get('body', '')
                    )
                    
                    self.state_manager.add_email(
                        message_id=msg_id,
                        subject=email_data.get('subject', ''),
                        sender=email_data.get('from', ''),
                        content=email_data.get('body', ''),
                        processed_content=processed_content,
                        category_id=category.id,
                        received_date=email_data.get('date')
                    )
        
    def prepare_training_data(
        self,
        min_samples_per_category: int = 10,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare training data from processed emails, ensuring balanced representation
        across categories.
        
        Args:
            min_samples_per_category: Minimum number of samples required per category
            test_size: Proportion of data to use for testing
            random_state: Random seed for reproducibility
            
        Returns:
            Tuple of (training_data, test_data) as pandas DataFrames
        """
        # Get all processed emails with their categories
        emails = self.state_manager.get_all_emails_with_categories()
        
        if not emails:
            logger.warning("No processed emails found in database")
            return pd.DataFrame(), pd.DataFrame()
            
        # Convert to DataFrame for easier processing
        data = []
        for email in emails:
            processed_content = self.email_processor.process_email_content(email.content)
            data.append({
                'email_id': email.id,
                'content': processed_content,
                'category': email.category.name if email.category else 'uncategorized'
            })
            
        df = pd.DataFrame(data)
        
        # Filter categories with sufficient samples
        category_counts = df['category'].value_counts()
        valid_categories = category_counts[category_counts >= min_samples_per_category].index
        df_filtered = df[df['category'].isin(valid_categories)]
        
        if df_filtered.empty:
            logger.warning(f"No categories with at least {min_samples_per_category} samples")
            return pd.DataFrame(), pd.DataFrame()
            
        # Split into train/test sets
        train_df, test_df = train_test_split(
            df_filtered,
            test_size=test_size,
            stratify=df_filtered['category'],
            random_state=random_state
        )
        
        return train_df, test_df
        
    def analyze_category_distribution(self) -> Dict[str, int]:
        """
        Analyze the distribution of emails across categories.
        
        Returns:
            Dictionary mapping category names to email counts
        """
        emails = self.state_manager.get_all_emails_with_categories()
        distribution = {}
        
        for email in emails:
            category = email.category.name if email.category else 'uncategorized'
            distribution[category] = distribution.get(category, 0) + 1
            
        return distribution
        
    def identify_ambiguous_categories(
        self,
        similarity_threshold: float = 0.8
    ) -> List[tuple[str, str, float]]:
        """
        Identify potentially ambiguous categories based on content similarity.
        
        Args:
            similarity_threshold: Threshold for considering categories as potentially ambiguous
            
        Returns:
            List of tuples (category1, category2, similarity_score)
        """
        categories = self.state_manager.get_all_categories()
        ambiguous_pairs = []
        
        for i, cat1 in enumerate(categories):
            for cat2 in categories[i+1:]:
                emails1 = self.state_manager.get_emails_by_category(cat1.id)
                emails2 = self.state_manager.get_emails_by_category(cat2.id)
                
                if not emails1 or not emails2:
                    continue
                    
                # Calculate similarity between category contents
                similarity = self.categorizer.calculate_category_similarity(
                    [e.content for e in emails1],
                    [e.content for e in emails2]
                )
                
                if similarity > similarity_threshold:
                    ambiguous_pairs.append((cat1.name, cat2.name, similarity))
                    
        return ambiguous_pairs 