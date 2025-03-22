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
from .categorizer import EmailCategorizer
from .imap_manager import IMAPManager

logger = logging.getLogger(__name__)

class PreTrainingManager:
    """Manages pre-training data preparation and analysis for the email categorization system."""
    
    def __init__(
        self,
        state_manager: SQLiteStateManager,
        email_processor: EmailProcessor,
        categorizer: EmailCategorizer,
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
        last_check_time = time.time()
        while True:
            try:
                current_time = time.time()
                if current_time - last_check_time > check_interval * 1.5:  # 50% over interval
                    logger.warning(f"Category check took longer than expected: {current_time - last_check_time:.1f}s")
                
                logger.info("Starting category change check")
                self._check_category_changes(lookback_days)
                last_check_time = time.time()
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
        # Get account from config
        account = self.email_processor.config_manager.accounts[0]
        
        # Connect to IMAP server
        client = self.imap_manager.connect(account)
        if not client:
            logger.error(f"Failed to connect to {account}")
            return
        
        try:
            # Get all category folders from config
            categories = account.categories
            since_date = datetime.now() - timedelta(days=lookback_days)
            
            for category in categories:
                # Get emails from this category's folder
                folder_emails = self.imap_manager.get_emails(
                    client,
                    category.foldername,
                    max_emails=0  # No limit
                )
                
                if len(folder_emails) > 1000:  # Arbitrary threshold for large folders
                    logger.warning(f"Large folder detected: {category.foldername} with {len(folder_emails)} emails")
                
                for msg_id, email_obj in folder_emails.items():
                    # Check if this email exists in our database
                    if not self.state_manager.is_email_processed(account.name, email_obj):
                        # Email doesn't exist - add it to database
                        logger.info(f"New email {msg_id} found in category {category.name}")
                        self.state_manager.mark_email_as_processed(
                            account.name,
                            email_obj,
                            category.name
                        )
        finally:
            # Disconnect from IMAP server
            self.imap_manager.disconnect(account.name)
        
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
        start_time = time.time()
        logger.debug(f"Starting training data preparation with min_samples={min_samples_per_category}, test_size={test_size}")
        
        # Get account from config
        account = self.email_processor.config_manager.accounts[0]
        logger.debug(f"Processing account: {account.name}")
        
        # Connect to IMAP server
        if not self.imap_manager.connect(account):
            logger.error(f"Failed to connect to {account}")
            return pd.DataFrame(), pd.DataFrame()
        
        try:
            # Get all category folders from config
            categories = account.categories
            logger.debug(f"Found {len(categories)} categories: {[c.name for c in categories]}")
            
            # Process emails from each category folder
            for category in categories:
                category_start_time = time.time()
                logger.debug(f"Processing category: {category.name} from folder: {category.foldername}")
                # Get emails from this category's folder
                folder_emails = self.imap_manager.fetch_emails_from_folder(category.foldername)
                logger.debug(f"Found {len(folder_emails)} emails in category {category.name}")
                
                if len(folder_emails) > 1000:  # Arbitrary threshold for large folders
                    logger.warning(f"Large category folder detected: {category.foldername} with {len(folder_emails)} emails")
                
                # Categorize emails in batches
                batch_size = 10
                for i in range(0, len(folder_emails), batch_size):
                    batch_start_time = time.time()
                    batch = folder_emails[i:i+batch_size]
                    logger.debug(f"Processing batch {i//batch_size + 1} of {(len(folder_emails) + batch_size - 1)//batch_size}")
                    
                    # Convert Email objects to dictionaries
                    email_dicts = [
                        {
                            'from': email.from_addr,
                            'to': email.to_addr,
                            'subject': email.subject,
                            'date': str(email.date),
                            'body': email.body
                        }
                        for email in batch
                    ]
                    results = self.categorizer.categorize_emails(email_dicts, categories)
                    
                    batch_time = time.time() - batch_start_time
                    if batch_time > 30:  # 30 seconds threshold for batch processing
                        logger.warning(f"Batch processing took longer than expected: {batch_time:.1f}s")
                    
                    for j, email_obj in enumerate(batch):
                        if j < len(results):
                            result = results[j]
                            category = result.get("category")
                            if category is None:
                                category = next((cat for cat in categories if cat.name == "INBOX"), categories[0])
                                logger.debug(f"Email {email_obj.message_id} had no category, defaulting to INBOX")
                            elif isinstance(category, str):
                                # Convert string category to Category object
                                category = next((cat for cat in categories if cat.name == category.upper()), 
                                             next((cat for cat in categories if cat.name == "INBOX"), categories[0]))
                                logger.debug(f"Converted string category '{category}' to Category object")
                            # Check if this email exists in our database
                            if not self.state_manager.is_email_processed(account.name, email_obj):
                                # Email doesn't exist - add it to database with category
                                logger.info(f"New email {email_obj.message_id} found in category {category.name}")
                                self.state_manager.mark_email_as_processed(
                                    account.name,
                                    email_obj,
                                    category
                                )
                
                category_time = time.time() - category_start_time
                if category_time > 300:  # 5 minutes threshold for category processing
                    logger.warning(f"Category {category.name} processing took longer than expected: {category_time:.1f}s")
                
        finally:
            # Disconnect from IMAP server
            self.imap_manager.disconnect(account.name)
            logger.debug("Disconnected from IMAP server")
        
        # Get all processed emails with their categories
        emails = self.state_manager.get_all_emails_with_categories()
        logger.debug(f"Retrieved {len(emails)} processed emails from database")
        
        if not emails:
            logger.warning("No processed emails found in database")
            return pd.DataFrame(), pd.DataFrame()
            
        # Convert to DataFrame for easier processing
        data = []
        for email, category in emails:
            if category:  # Only include emails with valid categories
                data.append({
                    'message_id': email.message_id,
                    'content': email.body,
                    'category': category.name
                })
            
        df = pd.DataFrame(data)
        logger.debug(f"Created DataFrame with {len(df)} rows")
        
        if df.empty:
            logger.warning("No valid categorized emails found")
            return pd.DataFrame(), pd.DataFrame()
        
        # Filter categories with sufficient samples
        category_counts = df['category'].value_counts()
        valid_categories = category_counts[category_counts >= min_samples_per_category].index
        df_filtered = df[df['category'].isin(valid_categories)]
        logger.debug(f"Category distribution after filtering: {category_counts.to_dict()}")
        logger.debug(f"Categories with sufficient samples: {list(valid_categories)}")
        
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
        logger.debug(f"Split data into {len(train_df)} training and {len(test_df)} test samples")
        
        total_time = time.time() - start_time
        if total_time > 600:  # 10 minutes threshold for total processing
            logger.warning(f"Total training data preparation took longer than expected: {total_time:.1f}s")
        
        return train_df, test_df
        
    def analyze_category_distribution(self) -> Dict[str, int]:
        """
        Analyze the distribution of emails across categories.
        
        Returns:
            Dictionary mapping category names to email counts
        """
        start_time = time.time()
        logger.debug("Starting category distribution analysis")
        emails = self.state_manager.get_all_emails_with_categories()
        distribution = {}
        
        for email, category in emails:
            category_name = category.name if category else 'uncategorized'
            distribution[category_name] = distribution.get(category_name, 0) + 1
            
        logger.debug(f"Category distribution: {distribution}")
        
        total_time = time.time() - start_time
        if total_time > 60:  # 1 minute threshold for distribution analysis
            logger.warning(f"Category distribution analysis took longer than expected: {total_time:.1f}s")
            
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
        start_time = time.time()
        logger.debug(f"Starting ambiguous category identification with threshold {similarity_threshold}")
        categories = self.state_manager.get_all_categories()
        ambiguous_pairs = []
        
        for i, cat1 in enumerate(categories):
            category_start_time = time.time()
            logger.debug(f"Analyzing category {cat1.name} for ambiguity")
            for cat2 in categories[i+1:]:
                emails1 = self.state_manager.get_emails_by_category(cat1.id)
                emails2 = self.state_manager.get_emails_by_category(cat2.id)
                
                if not emails1 or not emails2:
                    logger.debug(f"Skipping comparison between {cat1.name} and {cat2.name} - insufficient data")
                    continue
                    
                if len(emails1) > 1000 or len(emails2) > 1000:  # Arbitrary threshold for large categories
                    logger.warning(f"Large category detected in comparison: {cat1.name} ({len(emails1)}) or {cat2.name} ({len(emails2)})")
                    
                logger.debug(f"Comparing categories {cat1.name} ({len(emails1)} emails) and {cat2.name} ({len(emails2)} emails)")
                # Calculate similarity between category contents
                similarity = self.categorizer.calculate_category_similarity(
                    [e.content for e in emails1],
                    [e.content for e in emails2]
                )
                
                if similarity > similarity_threshold:
                    logger.debug(f"Found ambiguous pair: {cat1.name} - {cat2.name} (similarity: {similarity:.2f})")
                    ambiguous_pairs.append((cat1.name, cat2.name, similarity))
            
            category_time = time.time() - category_start_time
            if category_time > 300:  # 5 minutes threshold for category analysis
                logger.warning(f"Category {cat1.name} ambiguity analysis took longer than expected: {category_time:.1f}s")
                    
        logger.debug(f"Found {len(ambiguous_pairs)} ambiguous category pairs")
        
        total_time = time.time() - start_time
        if total_time > 900:  # 15 minutes threshold for total analysis
            logger.warning(f"Total ambiguous category identification took longer than expected: {total_time:.1f}s")
            
        return ambiguous_pairs 