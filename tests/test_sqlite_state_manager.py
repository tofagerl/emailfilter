"""Unit tests for the SQLite state manager."""

import os
import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest import mock
from mailmind.sqlite_state_manager import SQLiteStateManager
from mailmind.models import Email, Category

@pytest.fixture
def test_email():
    """Create a test email."""
    return Email(
        subject="Test Subject",
        from_addr="test@example.com",
        to_addr="user@example.com",
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        body="Test body",
        raw_message=b"Test raw message"
    )

@pytest.fixture
def test_db():
    """Create a test database."""
    return ":memory:"

@pytest.fixture
def state_manager(test_db):
    """Create a state manager with test database."""
    manager = SQLiteStateManager(db_file_path=test_db)
    manager._init_db()  # Explicitly initialize database
    return manager

def test_init_with_memory_db(test_db):
    """Test initialization with in-memory database."""
    manager = SQLiteStateManager(db_file_path=test_db)
    assert manager.db_file_path == test_db
    assert manager._persistent_connection is not None

def test_init_with_file_db(tmp_path):
    """Test initialization with file database."""
    db_path = os.path.join(tmp_path, "test.db")
    manager = SQLiteStateManager(db_file_path=db_path)
    assert manager.db_file_path == db_path
    assert os.path.exists(db_path)

def test_add_category(state_manager):
    """Test adding a category."""
    state_manager.add_category("TEST", "Test Folder")
    
    # Verify category was added
    conn = state_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE name = ?", ("TEST",))
    category = cursor.fetchone()
    assert category is not None
    assert category["name"] == "TEST"
    assert category["foldername"] == "Test Folder"

def test_generate_email_id(state_manager, test_email):
    """Test email ID generation."""
    account_name = "test_account"
    hash_id = state_manager._generate_email_id(account_name, test_email)
    assert isinstance(hash_id, str)
    assert len(hash_id) == 64  # SHA-256 hash length

def test_connection_pool(state_manager):
    """Test connection pool management."""
    # Get multiple connections
    connections = []
    for _ in range(state_manager._max_connections + 1):
        conn = state_manager._get_connection()
        assert conn is not None
        connections.append(conn)
    
    # Return connections to pool
    for conn in connections:
        state_manager._return_connection(conn)
    
    # Verify pool size
    assert len(state_manager._connection_pool) <= state_manager._max_connections

def test_is_connection_valid(state_manager):
    """Test connection validation."""
    conn = state_manager._create_connection()
    assert state_manager._is_connection_valid(conn)
    
    # Test invalid connection
    conn.close()
    assert not state_manager._is_connection_valid(conn)

def test_is_email_processed(state_manager, test_email):
    """Test checking if email is processed."""
    account_name = "test_account"
    
    # Initially should not be processed
    assert not state_manager.is_email_processed(account_name, test_email)
    
    # Mark as processed
    state_manager.mark_email_as_processed(account_name, test_email)
    
    # Should now be processed
    assert state_manager.is_email_processed(account_name, test_email)

def test_mark_email_as_processed(state_manager, test_email):
    """Test marking email as processed."""
    account_name = "test_account"
    category = "TEST"
    
    # Mark email as processed
    state_manager.mark_email_as_processed(account_name, test_email, category)
    
    # Verify in database
    conn = state_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM processed_emails WHERE account_name = ? AND category = ?",
        (account_name, category)
    )
    email_record = cursor.fetchone()
    assert email_record is not None
    assert email_record["subject"] == test_email.subject
    assert email_record["from_addr"] == test_email.from_addr
    assert email_record["category"] == category

def test_cleanup_old_entries(state_manager, test_email):
    """Test cleaning up old entries."""
    account_name = "test_account"
    
    # Add test email
    state_manager.mark_email_as_processed(account_name, test_email)
    
    # Modify timestamp to be old
    conn = state_manager._get_connection()
    cursor = conn.cursor()
    old_date = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE processed_emails SET processed_date = ? WHERE account_name = ?",
        (old_date, account_name)
    )
    conn.commit()
    
    # Clean up old entries
    state_manager.cleanup_old_entries(max_age_days=30)
    
    # Verify email was removed
    assert not state_manager.is_email_processed(account_name, test_email)

def test_get_processed_count(state_manager, test_email):
    """Test getting processed email count."""
    account_name = "test_account"
    
    # Initially should be 0
    assert state_manager.get_processed_count(account_name) == 0
    
    # Add test email
    state_manager.mark_email_as_processed(account_name, test_email)
    
    # Should now be 1
    assert state_manager.get_processed_count(account_name) == 1

def test_get_accounts(state_manager, test_email):
    """Test getting list of accounts."""
    account_names = ["account1", "account2"]
    
    # Add emails for different accounts
    for account in account_names:
        state_manager.mark_email_as_processed(account, test_email)
    
    # Get accounts
    accounts = state_manager.get_accounts()
    assert len(accounts) == 2
    assert all(account in accounts for account in account_names)

def test_delete_account_entries(state_manager, test_email):
    """Test deleting account entries."""
    account_name = "test_account"
    
    # Add test email
    state_manager.mark_email_as_processed(account_name, test_email)
    
    # Delete account entries
    deleted = state_manager.delete_account_entries(account_name)
    assert deleted == 1
    
    # Verify account has no entries
    assert state_manager.get_processed_count(account_name) == 0

def test_query_processed_emails(state_manager, test_email):
    """Test querying processed emails."""
    account_name = "test_account"
    category = "TEST"
    
    # Add test email
    state_manager.mark_email_as_processed(account_name, test_email, category)
    
    # Query with filters
    results = state_manager.query_processed_emails(
        account_name=account_name,
        from_addr=test_email.from_addr,
        category=category
    )
    
    assert len(results) == 1
    assert results[0]["subject"] == test_email.subject
    assert results[0]["category"] == category

def test_get_category_stats(state_manager, test_email):
    """Test getting category statistics."""
    account_name = "test_account"
    categories = ["CAT1", "CAT2"]
    
    # Add emails with different categories
    for category in categories:
        state_manager.mark_email_as_processed(account_name, test_email, category)
    
    # Get stats
    stats = state_manager.get_category_stats(account_name)
    assert len(stats) == 2
    assert all(category in stats for category in categories)
    assert all(stats[category] == 1 for category in categories)

def test_get_all_categories(state_manager):
    """Test getting all categories."""
    categories = [
        ("CAT1", "Test Category 1", "Folder1"),
        ("CAT2", "Test Category 2", "Folder2")
    ]
    
    # Add categories
    for name, desc, folder in categories:
        state_manager.add_category(name, folder)
    
    # Get all categories
    results = state_manager.get_all_categories()
    assert len(results) == 2
    assert all(cat["name"] in [c[0] for c in categories] for cat in results)

def test_error_handling(state_manager):
    """Test error handling."""
    # Test with invalid SQL
    with pytest.raises(Exception):
        state_manager._execute_with_connection(
            lambda conn: conn.execute("INVALID SQL")
        )
    
    # Test with closed connection
    conn = state_manager._create_connection()
    conn.close()
    assert not state_manager._is_connection_valid(conn) 