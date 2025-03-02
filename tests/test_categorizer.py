"""Tests for the categorizer module."""

import os
from unittest import mock

import pytest

from emailfilter import categorizer


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


def test_email_category_enum():
    """Test the EmailCategory enum."""
    assert str(categorizer.EmailCategory.SPAM) == "Spam"
    assert str(categorizer.EmailCategory.RECEIPTS) == "Receipts"
    assert str(categorizer.EmailCategory.PROMOTIONS) == "Promotions"
    assert str(categorizer.EmailCategory.UPDATES) == "Updates"
    assert str(categorizer.EmailCategory.INBOX) == "Inbox"


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_categorize_email(mock_create, mock_openai_response):
    """Test the categorize_email function."""
    # Test email
    email = {
        "from": "shop@example.com",
        "to": "user@example.com",
        "subject": "Your order has shipped",
        "body": "Your recent order #12345 has shipped and will arrive tomorrow."
    }
    
    # Mock OpenAI response for RECEIPTS
    mock_create.return_value = mock_openai_response("RECEIPTS")
    
    # Test categorization
    category = categorizer.categorize_email(email)
    assert category == categorizer.EmailCategory.RECEIPTS
    
    # Verify OpenAI API was called correctly
    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert kwargs["model"] == "gpt-4o-mini"  # Check for GPT-4o-mini model
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
    assert "Categorize the following email" in kwargs["messages"][1]["content"]
    assert email["from"] in kwargs["messages"][1]["content"]
    assert email["subject"] in kwargs["messages"][1]["content"]
    assert kwargs["temperature"] == 0.2


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("openai.chat.completions.create")
def test_categorize_email_unknown_response(mock_create, mock_openai_response):
    """Test the categorize_email function with an unknown response."""
    # Test email
    email = {
        "from": "user@example.com",
        "to": "friend@example.com",
        "subject": "Hello",
        "body": "Just saying hi!"
    }
    
    # Mock OpenAI response with unknown category
    mock_create.return_value = mock_openai_response("UNKNOWN")
    
    # Test categorization - should default to INBOX
    category = categorizer.categorize_email(email)
    assert category == categorizer.EmailCategory.INBOX


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("emailfilter.categorizer.categorize_email")
def test_batch_categorize_emails(mock_categorize_email):
    """Test the batch_categorize_emails function."""
    # Test emails
    emails = [
        {"subject": "Email 1"},
        {"subject": "Email 2"},
        {"subject": "Email 3"}
    ]
    
    # Mock categorize_email to return different categories
    categories = [
        categorizer.EmailCategory.INBOX,
        categorizer.EmailCategory.SPAM,
        categorizer.EmailCategory.PROMOTIONS
    ]
    mock_categorize_email.side_effect = categories
    
    # Test batch categorization
    result = categorizer.batch_categorize_emails(emails, batch_size=2)
    
    # Verify results
    assert len(result) == 3
    assert result[0]["email"] == emails[0]
    assert result[0]["category"] == "Inbox"
    assert result[1]["email"] == emails[1]
    assert result[1]["category"] == "Spam"
    assert result[2]["email"] == emails[2]
    assert result[2]["category"] == "Promotions"
    
    # Verify categorize_email was called for each email
    assert mock_categorize_email.call_count == 3


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("emailfilter.categorizer.categorize_email")
def test_categorize_and_filter(mock_categorize_email):
    """Test the categorize_and_filter function."""
    # Test emails
    emails = [
        {"subject": "Important"},
        {"subject": "Spam"},
        {"subject": "Newsletter"}
    ]
    
    # Mock categorize_email to return different categories
    categories = [
        categorizer.EmailCategory.INBOX,
        categorizer.EmailCategory.SPAM,
        categorizer.EmailCategory.PROMOTIONS
    ]
    mock_categorize_email.side_effect = categories
    
    # Test with no category filter (should return all)
    result = categorizer.categorize_and_filter(emails)
    
    # Verify all categories are present
    assert len(result) == len(categorizer.EmailCategory)
    assert len(result[categorizer.EmailCategory.INBOX]) == 1
    assert len(result[categorizer.EmailCategory.SPAM]) == 1
    assert len(result[categorizer.EmailCategory.PROMOTIONS]) == 1
    assert len(result[categorizer.EmailCategory.RECEIPTS]) == 0
    assert len(result[categorizer.EmailCategory.UPDATES]) == 0
    
    # Test with category filter
    mock_categorize_email.side_effect = categories  # Reset side effect
    result = categorizer.categorize_and_filter(
        emails, 
        categories=[categorizer.EmailCategory.INBOX]
    )
    
    # Verify only INBOX emails are present
    assert len(result[categorizer.EmailCategory.INBOX]) == 1
    assert result[categorizer.EmailCategory.INBOX][0] == emails[0]
    assert len(result[categorizer.EmailCategory.SPAM]) == 0
    assert len(result[categorizer.EmailCategory.PROMOTIONS]) == 0 