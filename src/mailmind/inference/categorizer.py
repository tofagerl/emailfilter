"""Email categorization using trained model."""

import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

import torch
from transformers import AutoTokenizer

from ..training.model import EmailCategorizationModel

# Configure logging
logger = logging.getLogger(__name__)

class EmailCategorizer:
    """Categorizes emails using trained model."""
    
    def __init__(self, model_dir: Optional[str] = None):
        """Initialize the email categorizer.
        
        Args:
            model_dir: Directory containing the trained model
        """
        if model_dir is None:
            model_dir = os.environ.get("MODEL_PATH", "models/email-classifier")
        
        self.model_dir = Path(model_dir)
        self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        
        # Load model and tokenizer
        self.model = EmailCategorizationModel.load(self.model_dir, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        
        logger.info(f"Loaded model from {model_dir} using {self.device} device")
    
    def _prepare_email_text(self, email: Dict[str, str]) -> str:
        """Prepare email text for the model.
        
        Args:
            email: Dictionary containing email fields
            
        Returns:
            Formatted email text
        """
        return f"""From: {email.get('from', '')}
To: {email.get('to', '')}
Subject: {email.get('subject', '')}
Date: {email.get('date', '')}
Body: {email.get('body', '')}"""
    
    def categorize_emails(self, emails: List[Dict[str, str]], batch_size: int = 8) -> List[Dict[str, Any]]:
        """Categorize a batch of emails.
        
        Args:
            emails: List of email dictionaries
            batch_size: Batch size for processing
            
        Returns:
            List of dictionaries with categorization results
        """
        results = []
        
        # Process in batches
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            batch_texts = [self._prepare_email_text(email) for email in batch]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model.forward(**inputs)
                predictions = outputs["predictions"].cpu().numpy()
                logits = outputs["logits"].cpu().numpy()
                probabilities = torch.nn.functional.softmax(torch.tensor(logits), dim=-1).numpy()
            
            # Convert predictions to categories
            for j, pred in enumerate(predictions):
                category = self.model.id_to_category[pred]
                confidence = float(probabilities[j][pred]) * 100
                
                results.append({
                    "category": category,
                    "confidence": confidence,
                    "reasoning": f"Model confidence: {confidence:.1f}%"
                })
        
        return results


# Global categorizer instance
_global_categorizer = None


def initialize_categorizer(model_dir: Optional[str] = None) -> None:
    """Initialize the global categorizer instance."""
    global _global_categorizer
    _global_categorizer = EmailCategorizer(model_dir)


def batch_categorize_emails_for_account(
    emails: List[Dict[str, str]],
    account: Any,
    batch_size: int = 8,
    model: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Categorize emails for an account (backward compatibility).
    
    Args:
        emails: List of email dictionaries
        account: Account object (ignored, kept for compatibility)
        batch_size: Batch size for processing
        model: Model name (ignored, kept for compatibility)
        
    Returns:
        List of dictionaries with categorization results
    """
    global _global_categorizer
    
    # Create categorizer if it doesn't exist
    if not _global_categorizer:
        initialize_categorizer()
    
    return _global_categorizer.categorize_emails(emails, batch_size) 