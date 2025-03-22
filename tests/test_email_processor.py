"""Unit tests for the email processor module."""

import pytest
from unittest import mock
from mailmind.email_processor import filter_emails, EmailProcessor
from mailmind.models import Email, EmailAccount, Category
from mailmind.config import ConfigManager
from mailmind.imap_manager import IMAPManager
from mailmind.sqlite_state_manager import SQLiteStateManager

@pytest.fixture
def mock_config():
    """Create a mock configuration manager."""
    config = mock.MagicMock(spec=ConfigManager)
    config.options = mock.MagicMock()
    config.options.move_emails = True
    config.options.model = "gpt-4"
    config.openai_api_key = "test-key"
    return config

@pytest.fixture
def mock_imap():
    """Create a mock IMAP manager."""
    return mock.MagicMock(spec=IMAPManager)

@pytest.fixture
def mock_state():
    """Create a mock state manager."""
    return mock.MagicMock(spec=SQLiteStateManager)

@pytest.fixture
def test_account():
    """Create a test email account."""
    return EmailAccount(
        name="test",
        email="test@example.com",
        password="test-pass",
        imap_server="imap.example.com",
        categories=[
            Category("INBOX", "Default inbox", "INBOX"),
            Category("WORK", "Work related", "Work"),
            Category("PERSONAL", "Personal emails", "Personal")
        ]
    )

@pytest.fixture
def test_emails():
    """Create test email data."""
    return [
        {"from": "work@example.com", "subject": "Meeting", "body": "Team meeting"},
        {"from": "friend@example.com", "subject": "Party", "body": "Weekend party"},
        {"from": "spam@example.com", "subject": "Win prize", "body": "You won!"}
    ]

@pytest.fixture
def test_email():
    """Create a test Email object."""
    return Email(
        subject="Test Subject",
        from_addr="test@example.com",
        to_addr="user@example.com",
        date="2024-03-22",
        body="Test body",
        raw_message=b"Test raw message"
    )

def test_filter_emails_no_filters(test_emails):
    """Test filter_emails with no filters."""
    filtered = filter_emails(test_emails)
    assert filtered == test_emails

def test_filter_emails_with_filters(test_emails):
    """Test filter_emails with filters."""
    filters = {"from": "example.com"}
    filtered = filter_emails(test_emails, filters)
    assert len(filtered) == 3  # All emails contain example.com
    assert all("example.com" in email["from"] for email in filtered)

def test_filter_emails_empty_list():
    """Test filter_emails with empty list."""
    filtered = filter_emails([])
    assert filtered == []

def test_email_processor_init(mock_config, mock_imap, mock_state):
    """Test EmailProcessor initialization."""
    processor = EmailProcessor(mock_config, mock_imap, mock_state)
    assert processor.config_manager == mock_config
    assert processor.imap_manager == mock_imap
    assert processor.state_manager == mock_state

def test_estimate_email_size(test_email):
    """Test email size estimation."""
    processor = EmailProcessor(mock.MagicMock())
    size = processor._estimate_email_size(test_email)
    assert size > 0

def test_should_process_email(test_email):
    """Test email processing size check."""
    processor = EmailProcessor(mock.MagicMock())
    
    # Test within size limit
    assert processor._should_process_email(test_email)
    
    # Test exceeding size limit
    large_email = Email(
        subject="Test Subject",
        from_addr="test@example.com",
        to_addr="user@example.com",
        date="2024-03-22",
        body="x" * (processor.max_email_size + 1),
        raw_message=b"x" * (processor.max_email_size + 1)
    )
    assert not processor._should_process_email(large_email)

def test_categorize_emails(mock_config, mock_imap, mock_state, test_account):
    """Test email categorization."""
    processor = EmailProcessor(mock_config, mock_imap, mock_state)
    
    # Create test emails
    emails = {
        1: Email(
            subject="Work meeting",
            from_addr="work@example.com",
            to_addr="user@example.com",
            date="2024-03-22",
            body="Team meeting",
            raw_message=b"Work meeting"
        ),
        2: Email(
            subject="Party",
            from_addr="friend@example.com",
            to_addr="user@example.com",
            date="2024-03-22",
            body="Weekend party",
            raw_message=b"Party"
        )
    }
    
    # Mock IMAP client
    mock_client = mock.MagicMock()
    
    # Mock categorizer response
    with mock.patch('mailmind.categorizer.batch_categorize_emails_for_account') as mock_categorize:
        mock_categorize.return_value = [
            {"category": "WORK"},
            {"category": "PERSONAL"}
        ]
        
        # Test categorization
        results = processor.categorize_emails(mock_client, emails, test_account)
        
        # Verify results
        assert len(results) == 2
        assert results[1][1] == "WORK"
        assert results[2][1] == "PERSONAL"

def test_process_categorized_emails(mock_config, mock_imap, mock_state, test_account):
    """Test processing of categorized emails."""
    processor = EmailProcessor(mock_config, mock_imap, mock_state)
    
    # Create test data
    mock_client = mock.MagicMock()
    categorized_emails = {
        1: (Email(
            subject="Work meeting",
            from_addr="work@example.com",
            to_addr="user@example.com",
            date="2024-03-22",
            body="Team meeting",
            raw_message=b"Work meeting"
        ), "WORK"),
        2: (Email(
            subject="Party",
            from_addr="friend@example.com",
            to_addr="user@example.com",
            date="2024-03-22",
            body="Weekend party",
            raw_message=b"Party"
        ), "PERSONAL")
    }
    
    # Mock IMAP manager move_email
    mock_imap.move_email.return_value = True
    
    # Test processing
    results = processor.process_categorized_emails(
        mock_client, 
        categorized_emails, 
        test_account
    )
    
    # Verify results
    assert results["WORK"] == 1
    assert results["PERSONAL"] == 1
    assert results["INBOX"] == 0
    
    # Verify move_email was called
    assert mock_imap.move_email.call_count == 2
    
    # Verify state manager was updated
    assert mock_state.mark_email_as_processed.call_count == 2

def test_process_categorized_emails_move_failure(mock_config, mock_imap, mock_state, test_account):
    """Test processing when email move fails."""
    processor = EmailProcessor(mock_config, mock_imap, mock_state)
    
    # Create test data
    mock_client = mock.MagicMock()
    categorized_emails = {
        1: (Email(
            subject="Work meeting",
            from_addr="work@example.com",
            to_addr="user@example.com",
            date="2024-03-22",
            body="Team meeting",
            raw_message=b"Work meeting"
        ), "WORK")
    }
    
    # Mock IMAP manager move_email to fail
    mock_imap.move_email.return_value = False
    
    # Test processing
    results = processor.process_categorized_emails(
        mock_client, 
        categorized_emails, 
        test_account
    )
    
    # Verify state manager was not updated
    mock_state.mark_email_as_processed.assert_not_called()
    
    # Verify results
    assert results["WORK"] == 0
    assert results["PERSONAL"] == 0
    assert results["INBOX"] == 0 