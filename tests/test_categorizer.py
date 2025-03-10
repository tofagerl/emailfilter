"""Tests for the categorizer module."""

import os
from unittest import mock

import pytest

from emailfilter import categorizer
from emailfilter.models import EmailAccount, Category


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    class MockChoice:
        def __init__(self, content):
            self.message = mock.MagicMock()
            self.message.content = content
    
    class MockResponse:
        def __init__(self, content):
            self.choices = [MockChoice(content)]
    
    return MockResponse


@pytest.fixture
def mock_account():
    """Create a mock account for testing."""
    return EmailAccount(
        name="Test Account",
        email_address="test@example.com",
        password="password",
        imap_server="imap.example.com",
        categories=[
            Category("SPAM", "Unwanted emails", "[Spam]"),
            Category("RECEIPTS", "Order confirmations", "[Receipts]"),
            Category("PROMOTIONS", "Marketing emails", "[Promotions]"),
            Category("UPDATES", "Notifications", "[Updates]"),
            Category("INBOX", "Important emails", "INBOX")
        ]
    )


def test_email_category_enum():
    """Test the EmailCategory enum."""
    assert str(categorizer.EmailCategory.SPAM) == "Spam"
    assert str(categorizer.EmailCategory.RECEIPTS) == "Receipts"
    assert str(categorizer.EmailCategory.PROMOTIONS) == "Promotions"
    assert str(categorizer.EmailCategory.UPDATES) == "Updates"
    assert str(categorizer.EmailCategory.INBOX) == "Inbox"


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.OpenAI")
def test_initialize_openai_client(mock_openai):
    """Test the initialize_openai_client function."""
    # Test with API key directly
    categorizer.initialize_openai_client(api_key="direct_key")
    mock_openai.assert_called_with(api_key="direct_key")
    
    # Reset mock
    mock_openai.reset_mock()
    
    # Test with environment variable
    categorizer.initialize_openai_client()
    mock_openai.assert_called_with(api_key="test_key")
    
    # Reset mock and client
    mock_openai.reset_mock()
    categorizer.client = None
    
    # Test with config file
    with mock.patch("builtins.open", mock.mock_open(read_data='openai_api_key: "config_key"')):
        categorizer.initialize_openai_client(config_path="config.yaml")
    mock_openai.assert_called_with(api_key="config_key")


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_batch_categorize_emails_for_account(mock_create, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function."""
    # Initialize the client
    categorizer.initialize_openai_client()
    
    # Test emails
    emails = [
        {
            "from": "shop@example.com",
            "to": "user@example.com",
            "subject": "Your order has shipped",
            "body": "Your recent order #12345 has shipped and will arrive tomorrow."
        },
        {
            "from": "spam@example.com",
            "to": "user@example.com",
            "subject": "Win a prize!",
            "body": "You've won a million dollars! Click here to claim."
        }
    ]
    
    # Mock OpenAI response with JSON objects
    mock_create.return_value = mock_openai_response(
        '{"category": "RECEIPTS", "confidence": 95, "reasoning": "This is an order confirmation"}\n'
        '{"category": "SPAM", "confidence": 98, "reasoning": "This is clearly spam"}'
    )
    
    # Test batch categorization
    results = categorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 2
    assert results[0]["category"] == "RECEIPTS"
    assert results[0]["confidence"] == 95
    assert "order confirmation" in results[0]["reasoning"]
    assert results[1]["category"] == "SPAM"
    assert results[1]["confidence"] == 98
    assert "clearly spam" in results[1]["reasoning"]
    
    # Verify OpenAI API was called correctly
    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert kwargs["model"] == "gpt-4o-mini"  # Check for default model
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert "categorize emails" in kwargs["messages"][0]["content"].lower()
    assert kwargs["messages"][1]["role"] == "user"
    assert "Categorize the following emails" in kwargs["messages"][1]["content"]
    assert emails[0]["from"] in kwargs["messages"][1]["content"]
    assert emails[1]["subject"] in kwargs["messages"][1]["content"]


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_batch_categorize_emails_for_account_invalid_response(mock_create, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function with invalid response."""
    # Initialize the client
    categorizer.initialize_openai_client()
    
    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]
    
    # Mock OpenAI response with invalid JSON
    mock_create.return_value = mock_openai_response("This is not JSON")
    
    # Test batch categorization - should default to INBOX
    results = categorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 1
    assert results[0]["category"] == "INBOX"
    assert results[0]["confidence"] == 0
    assert "Failed to parse response" in results[0]["reasoning"]


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_batch_categorize_emails_for_account_invalid_category(mock_create, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function with invalid category."""
    # Initialize the client
    categorizer.initialize_openai_client()
    
    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]
    
    # Mock OpenAI response with invalid category
    mock_create.return_value = mock_openai_response(
        '{"category": "INVALID", "confidence": 95, "reasoning": "This is an invalid category"}'
    )
    
    # Test batch categorization - should default to INBOX
    results = categorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 1
    assert results[0]["category"] == "INBOX"
    assert results[0]["confidence"] == 0
    assert "Failed to parse response" in results[0]["reasoning"]


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_batch_categorize_emails_for_account_api_error(mock_create, mock_account):
    """Test the batch_categorize_emails_for_account function with API error."""
    # Initialize the client
    categorizer.initialize_openai_client()
    
    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]
    
    # Mock OpenAI API error
    mock_create.side_effect = Exception("API error")
    
    # Test batch categorization - should handle error gracefully
    results = categorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 1
    assert results[0]["category"] == "INBOX"
    assert results[0]["confidence"] == 0
    assert "API error" in results[0]["reasoning"] 