"""Tests for the categorizer module."""

import os
import re
import json
from unittest import mock

import pytest

from mailmind.categorizer import Category, EmailAccount, EmailCategory
from mailmind.categorizer import EmailCategorizer


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    class MockMessage:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"

    class MockChoice:
        def __init__(self, content):
            self.message = MockMessage(content)
            self.index = 0
            self.finish_reason = "stop"

    class MockResponse:
        def __init__(self, content):
            self.choices = [MockChoice(content)]
            self.model = "gpt-4"
            self.object = "chat.completion"
            self.created = 1234567890
            self.usage = {"total_tokens": 100}

    def create_response(content):
        response = MockResponse(content)
        response.choices[0].message.content = content
        return response

    return create_response


@pytest.fixture
def mock_account():
    """Create a mock account for testing."""
    return EmailAccount(
        name="Test Account",
        email="test@example.com",
        password="password",
        imap_server="imap.example.com",
        categories=[
            Category("INBOX", "Default inbox", "INBOX"),
            Category("WORK", "Work related emails", "Work"),
            Category("PERSONAL", "Personal emails", "Personal"),
            Category("SHOPPING", "Shopping related emails", "Shopping"),
            Category("TRAVEL", "Travel related emails", "Travel")
        ]
    )


@pytest.fixture
def mock_categorizer():
    """Create a mock EmailCategorizer instance."""
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
        cat = EmailCategorizer()
        cat.client = mock.MagicMock()
        return cat


@pytest.fixture
def sample_emails():
    """Sample emails for testing."""
    return [
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


@pytest.fixture
def category_objects():
    """Create Category objects for testing."""
    return [
        Category("SPAM", "Unwanted emails", "[Spam]"),
        Category("RECEIPTS", "Order confirmations", "[Receipts]"),
        Category("PROMOTIONS", "Marketing emails", "[Promotions]"),
        Category("UPDATES", "Notifications", "[Updates]"),
        Category("INBOX", "Important emails", "INBOX")
    ]


def test_email_category_enum():
    """Test the EmailCategory enum."""
    assert str(EmailCategory.SPAM) == "Spam"
    assert str(EmailCategory.RECEIPTS) == "Receipts"
    assert str(EmailCategory.PROMOTIONS) == "Promotions"
    assert str(EmailCategory.UPDATES) == "Updates"
    assert str(EmailCategory.INBOX) == "Inbox"


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("mailmind.categorizer.OpenAI")
def test_initialize_openai_client(mock_openai):
    """Test the initialize_openai_client function."""
    # Reset the global categorizer
    EmailCategorizer._global_categorizer = None
    
    # Test with API key directly
    EmailCategorizer.initialize_openai_client(api_key="direct_key")
    mock_openai.assert_called_with(api_key="direct_key")
    
    # Reset mock and global categorizer
    mock_openai.reset_mock()
    EmailCategorizer._global_categorizer = None
    
    # Test with environment variable
    EmailCategorizer.initialize_openai_client()
    mock_openai.assert_called_with(api_key="test_key")
    
    # Reset mock and global categorizer
    mock_openai.reset_mock()
    EmailCategorizer._global_categorizer = None
    
    # Test with config file
    with mock.patch("builtins.open", mock.mock_open(read_data='openai_api_key: "config_key"')):
        EmailCategorizer.initialize_openai_client(config_path="config.yaml")
    mock_openai.assert_called_with(api_key="config_key")


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("mailmind.categorizer.OpenAI")
def test_batch_categorize_emails_for_account(mock_openai, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function."""
    # Create a mock categorizer
    cat = EmailCategorizer()

    # Mock the OpenAI client
    mock_client = mock.MagicMock()
    response = mock_openai_response(
        '{"category": "RECEIPTS", "confidence": 95, "reasoning": "This is an order confirmation"}\n'
        '{"category": "SPAM", "confidence": 98, "reasoning": "This is clearly spam"}'
    )
    mock_client.chat.completions.create.return_value = response
    mock_openai.return_value = mock_client

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

    # Test batch categorization
    results = EmailCategorizer.batch_categorize_emails_for_account(emails, mock_account)

    # Verify results
    assert len(results) == 2
    assert isinstance(results[0]["category"], Category)
    assert results[0]["category"].name == "INBOX"  # Since RECEIPTS is not in mock_account categories
    assert results[0]["confidence"] == 0  # Confidence is 0 for fallback category
    assert "invalid category" in results[0]["reasoning"].lower()
    assert isinstance(results[1]["category"], Category)
    assert results[1]["category"].name == "INBOX"  # Since SPAM is not in mock_account categories
    assert results[1]["confidence"] == 0  # Confidence is 0 for fallback category
    assert "invalid category" in results[1]["reasoning"].lower()


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("mailmind.categorizer.OpenAI")
def test_batch_categorize_emails_for_account_invalid_response(mock_openai, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function with invalid response."""
    # Create a mock categorizer
    cat = EmailCategorizer()
    
    # Mock the OpenAI client
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = mock_openai_response("This is not JSON")
    mock_openai.return_value = mock_client
    
    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]
    
    # Test batch categorization - should default to INBOX
    results = EmailCategorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 1
    assert isinstance(results[0]["category"], Category)
    assert results[0]["category"].name == "INBOX"
    assert results[0]["confidence"] == 0
    assert "failed to parse" in results[0]["reasoning"].lower() or "missing from response" in results[0]["reasoning"].lower()


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("mailmind.categorizer.OpenAI")
def test_batch_categorize_emails_for_account_invalid_category(mock_openai, mock_openai_response, mock_account):
    """Test the batch_categorize_emails_for_account function with invalid category."""
    # Create a mock categorizer
    cat = EmailCategorizer()
    
    # Mock the OpenAI client
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = mock_openai_response(
        '{"category": "INVALID", "confidence": 95, "reasoning": "This is an invalid category"}'
    )
    mock_openai.return_value = mock_client
    
    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]
    
    # Test batch categorization - should default to INBOX for invalid category
    results = EmailCategorizer.batch_categorize_emails_for_account(emails, mock_account)
    
    # Verify results
    assert len(results) == 1
    assert isinstance(results[0]["category"], Category)
    assert results[0]["category"].name == "INBOX"
    assert results[0]["confidence"] == 0
    assert "invalid category" in results[0]["reasoning"].lower() or "failed to parse" in results[0]["reasoning"].lower()


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
@mock.patch("mailmind.categorizer.OpenAI")
def test_batch_categorize_emails_for_account_api_error(mock_openai, mock_account):
    """Test the batch_categorize_emails_for_account function with API error."""
    # Create a mock categorizer
    cat = EmailCategorizer()

    # Mock the OpenAI client to raise an APIError
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = EmailCategorizer.APIError("API error")
    mock_openai.return_value = mock_client

    # Test emails
    emails = [
        {
            "from": "user@example.com",
            "to": "friend@example.com",
            "subject": "Hello",
            "body": "Just saying hi!"
        }
    ]

    # Test batch categorization - should default to INBOX
    results = EmailCategorizer.batch_categorize_emails_for_account(emails, mock_account)

    # Verify results
    assert len(results) == 1
    assert isinstance(results[0]["category"], Category)
    assert results[0]["category"].name == "INBOX"
    assert results[0]["confidence"] == 0
    assert "api error" in results[0]["reasoning"].lower()


# Tests for the EmailCategorizer class methods

def test_prepare_category_info(mock_categorizer, category_objects):
    """Test the _prepare_category_info method."""
    # Call the method
    category_info = mock_categorizer._prepare_category_info(category_objects)
    
    # Verify results
    assert len(category_info) == 5
    assert category_info[0]["name"] == "SPAM"
    assert category_info[0]["description"] == "Unwanted emails"
    assert category_info[0]["folder"] == "[Spam]"
    assert category_info[1]["name"] == "RECEIPTS"
    assert category_info[2]["name"] == "PROMOTIONS"
    assert category_info[3]["name"] == "UPDATES"
    assert category_info[4]["name"] == "INBOX"


def test_create_system_prompt(mock_categorizer, category_objects):
    """Test the _create_system_prompt method."""
    # Call the method
    system_prompt = mock_categorizer._create_system_prompt(category_objects)
    
    # Verify results
    assert "You are an email categorization assistant" in system_prompt
    assert "SPAM" in system_prompt
    assert "RECEIPTS" in system_prompt
    assert "PROMOTIONS" in system_prompt
    assert "UPDATES" in system_prompt
    assert "INBOX" in system_prompt
    assert "Unwanted emails" in system_prompt
    assert "Order confirmations" in system_prompt
    assert "Marketing emails" in system_prompt
    assert "Notifications" in system_prompt
    assert "Important emails" in system_prompt
    assert "[Spam]" in system_prompt
    assert "[Receipts]" in system_prompt
    assert "[Promotions]" in system_prompt
    assert "[Updates]" in system_prompt


def test_create_user_prompt(mock_categorizer, sample_emails):
    """Test the _create_user_prompt method."""
    # Call the method
    user_prompt = mock_categorizer._create_user_prompt(sample_emails, 2)
    
    # Verify results
    assert "Categorize the following emails" in user_prompt
    assert "Email 1:" in user_prompt
    assert "Email 2:" in user_prompt
    assert "From: shop@example.com" in user_prompt
    assert "From: spam@example.com" in user_prompt
    assert "Subject: Your order has shipped" in user_prompt
    assert "Subject: Win a prize!" in user_prompt
    assert "Body: Your recent order" in user_prompt
    assert "Body: You've won a million dollars" in user_prompt
    
    # Test with batch_size smaller than emails
    user_prompt = mock_categorizer._create_user_prompt(sample_emails, 1)
    assert "Email 1:" in user_prompt
    assert "Email 2:" not in user_prompt
    assert "From: shop@example.com" in user_prompt
    assert "From: spam@example.com" not in user_prompt


def test_call_api(mock_categorizer, mock_openai_response):
    """Test the _call_api method."""
    # Mock the chat.completions.create method
    mock_categorizer.client.chat.completions.create.return_value = mock_openai_response("Test response")
    
    # Call the method
    response = mock_categorizer._call_api("Test prompt")
    
    # Verify results
    assert response == "Test response"
    mock_categorizer.client.chat.completions.create.assert_called_once()
    
    # Verify OpenAI API was called correctly
    args, kwargs = mock_categorizer.client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4"
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == mock_categorizer.system_prompt
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "Test prompt"
    
    # Test with client not initialized
    mock_categorizer.client = None
    with pytest.raises(EmailCategorizer.APIError, match="OpenAI client not initialized"):
        mock_categorizer._call_api("Test prompt")


def test_extract_json_objects(mock_categorizer):
    """Test the _extract_json_objects method."""
    # Test with valid JSON objects
    response_text = 'Some text {"key1": "value1"} more text {"key2": "value2"}'
    json_objects = mock_categorizer._extract_json_objects(response_text)
    assert len(json_objects) == 2
    assert json_objects[0] == '{"key1": "value1"}'
    assert json_objects[1] == '{"key2": "value2"}'
    
    # Test with no JSON objects
    response_text = "No JSON objects here"
    json_objects = mock_categorizer._extract_json_objects(response_text)
    assert len(json_objects) == 0
    
    # Test with nested JSON objects
    # Note: The regex pattern only extracts simple JSON objects without nested braces
    response_text = '{"outer": {"inner": "value"}}'
    json_objects = mock_categorizer._extract_json_objects(response_text)
    # The current implementation will only extract the inner object
    # This is a limitation of the simple regex pattern used
    assert len(json_objects) == 1
    assert "inner" in json_objects[0]
    assert "value" in json_objects[0]


def test_validate_category(mock_categorizer):
    """Test the _validate_category method."""
    # Test with valid category
    valid_categories = ["SPAM", "INBOX", "RECEIPTS"]
    result = {"category": "spam", "confidence": 95}
    categories = [
        Category(name='SPAM', description='Spam emails', foldername='Spam'),
        Category(name='INBOX', description='Default inbox', foldername='INBOX'),
        Category(name='RECEIPTS', description='Receipt emails', foldername='Receipts')
    ]
    normalized = mock_categorizer._validate_category(result, valid_categories, categories)
    assert normalized["category"].name == "SPAM"  # Should be uppercase
    
    # Test with invalid category
    result = {"category": "INVALID", "confidence": 95}
    with mock.patch("mailmind.categorizer.logger") as mock_logger:
        normalized = mock_categorizer._validate_category(result, valid_categories, categories)
        assert normalized["category"].name == "INBOX"  # Should default to INBOX
        mock_logger.warning.assert_called_once_with("Invalid category: INVALID, defaulting to INBOX")
    
    # Test with missing category
    result = {"confidence": 95}
    normalized = mock_categorizer._validate_category(result, valid_categories, categories)
    assert normalized["category"].name == "INBOX"  # Should default to INBOX


def test_parse_response(mock_categorizer, category_objects):
    """Test the _parse_response method."""
    # Test with valid JSON response
    response_text = '{"category": "RECEIPTS", "confidence": 95, "reasoning": "This is a receipt"}'
    results = mock_categorizer._parse_response(response_text, category_objects, 1)
    assert len(results) == 1
    assert results[0]["category"].name == "RECEIPTS"
    assert results[0]["confidence"] == 95
    assert results[0]["reasoning"] == "This is a receipt"
    
    # Test with multiple JSON objects
    response_text = '{"category": "RECEIPTS", "confidence": 95} {"category": "SPAM", "confidence": 98}'
    results = mock_categorizer._parse_response(response_text, category_objects, 2)
    assert len(results) == 2
    assert results[0]["category"].name == "RECEIPTS"
    assert results[1]["category"].name == "SPAM"
    
    # Test with invalid JSON
    with mock.patch.object(mock_categorizer, "_extract_json_objects", return_value=["invalid json"]):
        with mock.patch.object(mock_categorizer, "_parse_json_object", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            with mock.patch("mailmind.categorizer.logger") as mock_logger:
                results = mock_categorizer._parse_response("invalid", category_objects, 1)
                assert len(results) == 1
                assert results[0]["category"].name == "INBOX"
                assert results[0]["confidence"] == 0
                assert "Failed to parse response" in results[0]["reasoning"]
                mock_logger.error.assert_called()
    
    # Test with fewer results than batch_size
    response_text = '{"category": "RECEIPTS", "confidence": 95}'
    results = mock_categorizer._parse_response(response_text, category_objects, 2)
    assert len(results) == 2
    assert results[0]["category"].name == "RECEIPTS"
    assert results[1]["category"].name == "INBOX"
    assert "Missing from response" in results[1]["reasoning"] 