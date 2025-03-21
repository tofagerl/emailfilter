import pytest
from mailmind.pre_training import PreTrainingManager
from mailmind.email_processor import EmailProcessor
from mailmind.categorizer import EmailCategorizer
from mailmind.imap_manager import IMAPManager
from mailmind.sqlite_state_manager import SQLiteStateManager
from mailmind.models import EmailAccount
from mailmind.config_manager import ConfigManager

def test_email_categorization_flow(mock_config, mock_imap):
    """Test the complete email categorization flow."""
    config_manager = ConfigManager(mock_config)
    account = config_manager.accounts[0]
    
    # Initialize components
    imap_manager = IMAPManager()
    state_manager = SQLiteStateManager(':memory:')
    email_processor = EmailProcessor(config_manager, imap_manager, state_manager)
    categorizer = EmailCategorizer(config_manager)
    
    # Connect to IMAP
    assert imap_manager.connect(account)
    
    # Process emails
    pre_training = PreTrainingManager(state_manager, email_processor, categorizer, imap_manager)
    pre_training.prepare_training_data()
    
    # Verify emails were processed
    processed_emails = state_manager.get_all_emails_with_categories()
    assert len(processed_emails) > 0
    
    # Verify categories were assigned
    for email in processed_emails:
        assert email.category is not None
        assert email.folder in [cat.foldername for cat in account.categories]

def test_category_distribution(mock_config, mock_imap):
    """Test that emails are distributed across categories."""
    config_manager = ConfigManager(mock_config)
    account = config_manager.accounts[0]
    
    # Initialize components
    imap_manager = IMAPManager()
    state_manager = SQLiteStateManager(':memory:')
    email_processor = EmailProcessor(config_manager, imap_manager, state_manager)
    categorizer = EmailCategorizer(config_manager)
    
    # Connect to IMAP
    assert imap_manager.connect(account)
    
    # Process emails
    pre_training = PreTrainingManager(state_manager, email_processor, categorizer, imap_manager)
    pre_training.prepare_training_data()
    
    # Get category distribution
    processed_emails = state_manager.get_all_emails_with_categories()
    categories = {cat.foldername: 0 for cat in account.categories}
    
    for email in processed_emails:
        categories[email.folder] += 1
    
    # Verify distribution
    total_emails = sum(categories.values())
    assert total_emails > 0
    
    # Check that emails are distributed across categories
    non_empty_categories = sum(1 for count in categories.values() if count > 0)
    assert non_empty_categories >= 2  # At least 2 categories should have emails

def test_training_data_preparation(mock_config, mock_imap):
    """Test preparation of training data."""
    config_manager = ConfigManager(mock_config)
    account = config_manager.accounts[0]
    
    # Initialize components
    imap_manager = IMAPManager()
    state_manager = SQLiteStateManager(':memory:')
    email_processor = EmailProcessor(config_manager, imap_manager, state_manager)
    categorizer = EmailCategorizer(config_manager)
    
    # Connect to IMAP
    assert imap_manager.connect(account)
    
    # Process emails
    pre_training = PreTrainingManager(state_manager, email_processor, categorizer, imap_manager)
    pre_training.prepare_training_data()
    
    # Verify training data
    processed_emails = state_manager.get_all_emails_with_categories()
    assert len(processed_emails) > 0
    
    # Check that each email has required fields
    for email in processed_emails:
        assert email.message_id is not None
        assert email.subject is not None
        assert email.body is not None
        assert email.category is not None
        assert email.folder is not None 