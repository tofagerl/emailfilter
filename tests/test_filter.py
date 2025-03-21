"""Tests for the filter module."""

from mailmind.email_processor import filter_emails


def test_filter_emails():
    """Test the filter_emails function."""
    # Sample test data
    emails = [
        {"from": "user@example.com", "subject": "Hello", "body": "Test message"},
        {"from": "other@test.com", "subject": "Meeting", "body": "Let's meet"},
        {"from": "user@example.com", "subject": "Update", "body": "Project update"},
    ]
    
    # Test with no filters
    assert filter_emails(emails) == emails
    
    # Test with from filter
    filtered = filter_emails(emails, {"from": "example.com"})
    assert len(filtered) == 2
    assert all("example.com" in email["from"] for email in filtered)
    
    # Test with subject filter
    filtered = filter_emails(emails, {"subject": "Meeting"})
    assert len(filtered) == 1
    assert filtered[0]["subject"] == "Meeting"
    
    # Test with multiple filters
    filtered = filter_emails(emails, {"from": "example.com", "subject": "Update"})
    assert len(filtered) == 1
    assert filtered[0]["from"] == "user@example.com"
    assert filtered[0]["subject"] == "Update" 