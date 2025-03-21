from typing import List, Dict, Optional
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

from .models import Email, Category
from .sqlite_state_manager import SQLiteStateManager
from .email_processor import EmailProcessor
from .categorizer import Categorizer

logger = logging.getLogger(__name__)

class PreTrainingManager:
    """Manages pre-training data preparation and analysis for the email categorization system."""
    
    def __init__(
        self,
        state_manager: SQLiteStateManager,
        email_processor: EmailProcessor,
        categorizer: Categorizer
    ):
        self.state_manager = state_manager
        self.email_processor = email_processor
        self.categorizer = categorizer
        
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