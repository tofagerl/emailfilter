import pytest
import imaplib
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import email.message
from email.mime.text import MIMEText
import openai
from mailmind.models import Category, Email
from mailmind.sqlite_state_manager import SQLiteStateManager
import sqlite3
import tempfile
import os
import yaml
import uuid

@pytest.fixture
def mock_config():
    """Create a mock configuration file for testing."""
    config = {
        'openai_api_key': 'test-key',
        'openai': {
            'model': 'gpt-4',
            'temperature': 0.7,
            'max_tokens': 1000
        },
        'accounts': [{
            'name': 'test',
            'email': 'test@example.com',
            'password': 'test-pass',
            'imap_server': 'imap.example.com',
            'imap_port': 993,
            'ssl': True,
            'folders': ['INBOX', 'Work', 'Personal', 'Shopping', 'Travel'],
            'categories': [
                {
                    'name': 'WORK',
                    'description': 'Work related emails',
                    'foldername': 'Work'
                },
                {
                    'name': 'PERSONAL',
                    'description': 'Personal emails',
                    'foldername': 'Personal'
                },
                {
                    'name': 'SHOPPING',
                    'description': 'Shopping related emails',
                    'foldername': 'Shopping'
                },
                {
                    'name': 'TRAVEL',
                    'description': 'Travel related emails',
                    'foldername': 'Travel'
                }
            ]
        }],
        'processing': {
            'batch_size': 10,
            'lookback_days': 30,
            'min_samples_per_category': 5,
            'test_size': 0.2
        }
    }
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        temp_path = f.name
    
    yield temp_path
    
    # Clean up
    os.unlink(temp_path)

class MockIMAPServer:
    """Mock IMAP server for testing."""

    def __init__(self):
        """Initialize the mock server."""
        self._logged_in = False
        self._current_folder = None
        self._folders = {
            'INBOX': [],
            'Work': [],
            'Personal': [],
            'Shopping': [],
            'Travel': []
        }
        self._create_test_emails()

    def _create_test_emails(self):
        """Create test emails for each folder."""
        for folder in self._folders:
            for i in range(5):
                self._folders[folder].append({
                    'id': f'{folder}_{i}',
                    'subject': f'Test email {i} in {folder}',
                    'body': f'This is test email {i} in {folder}',
                    'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000'),
                    'flags': []
                })

    def login(self, username, password):
        """Mock login."""
        self._logged_in = True
        return ('OK', [b'Logged in'])

    def logout(self):
        """Mock logout."""
        self._logged_in = False
        self._current_folder = None
        return ('OK', [b'Logged out'])

    def select(self, folder_name):
        """Mock folder selection."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        if folder_name not in self._folders:
            return ('NO', [b'Folder does not exist'])
        self._current_folder = folder_name
        return ('OK', [b'Selected'])

    def list(self, directory='""', pattern='*'):
        """Mock folder listing."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        return ('OK', [(b'()', b'/', folder.encode()) for folder in self._folders.keys()])

    def search(self, charset, *criteria):
        """Mock email search."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        if not self._current_folder:
            return ('NO', [b'No folder selected'])
        message_ids = [email['id'].encode() for email in self._folders[self._current_folder]]
        return ('OK', [b' '.join(message_ids)])

    def fetch(self, message_set, message_parts):
        """Mock email fetching."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        if not self._current_folder:
            return ('NO', [b'No folder selected'])
        
        result = []
        for msg_id in message_set.split():
            msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
            email = next((e for e in self._folders[self._current_folder] if e['id'] == msg_id_str), None)
            if email:
                msg = MIMEText(email['body'])
                msg['Subject'] = email['subject']
                msg['Date'] = email['date']
                msg['Message-ID'] = email['id']
                result.append((
                    msg_id_str.encode(),
                    {
                        b'BODY.PEEK[]': msg.as_bytes(),
                        b'FLAGS': email['flags'],
                        b'ENVELOPE': (
                            email['date'].encode(),
                            email['subject'].encode(),
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None
                        )
                    }
                ))
        return ('OK', result)

    def copy(self, message_set, new_folder):
        """Mock email copying."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        if not self._current_folder:
            return ('NO', [b'No folder selected'])
        if new_folder not in self._folders:
            return ('NO', [b'Folder does not exist'])
        
        for msg_id in message_set.split():
            email = next((e for e in self._folders[self._current_folder] if e['id'] == msg_id), None)
            if email:
                self._folders[new_folder].append(email.copy())
        return ('OK', [b'Copied'])

    def create(self, folder_name):
        """Mock folder creation."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        if folder_name in self._folders:
            return ('NO', [b'Folder already exists'])
        self._folders[folder_name] = []
        return ('OK', [b'Created'])

    def noop(self):
        """Mock noop command."""
        if not self._logged_in:
            return ('NO', [b'Not logged in'])
        return ('OK', [b'NOOP completed'])

@pytest.fixture
def mock_imap(monkeypatch):
    """Create a mock IMAP server."""
    mock_server = MockIMAPServer()

    def mock_imap4_ssl(host, port=993):
        if host != 'imap.example.com':
            raise OSError("[Errno 8] nodename nor servname provided, or not known")
        return mock_server

    def mock_imapclient(host, port=993, ssl=True):
        if host != 'imap.example.com':
            raise OSError("[Errno 8] nodename nor servname provided, or not known")
        return mock_server

    monkeypatch.setattr('imaplib.IMAP4_SSL', mock_imap4_ssl)
    monkeypatch.setattr('imapclient.IMAPClient', mock_imapclient)
    return mock_server

@pytest.fixture
def mock_openai():
    with patch('openai.ChatCompletion.create') as mock_chat:
        def side_effect(messages, **kwargs):
            content = messages[-1]['content'].lower()
            response = {
                'choices': [{
                    'message': {
                        'content': 'Work'
                        if 'deadline' in content or 'meeting' in content
                        else 'Personal'
                        if 'family' in content or 'dinner' in content
                        else 'Shopping'
                        if 'order' in content or 'shipped' in content
                        else 'Unknown'
                    }
                }]
            }
            return response
        
        mock_chat.side_effect = side_effect
        yield mock_chat

@pytest.fixture
def temp_db():
    # Create a temporary database file
    fd, path = tempfile.mkstemp()
    os.close(fd)
    
    # Initialize the database
    state_manager = SQLiteStateManager(db_file_path=path)
    
    yield path
    
    # Cleanup
    os.unlink(path)

@pytest.fixture
def categories(temp_db):
    state_manager = SQLiteStateManager(db_file_path=temp_db)
    categories = [
        Category(name='Work', description='Work related emails', foldername='Work'),
        Category(name='Personal', description='Personal emails', foldername='Personal'),
        Category(name='Shopping', description='Shopping related emails', foldername='Shopping'),
        Category(name='Travel', description='Travel related emails', foldername='Travel')
    ]
    
    for category in categories:
        state_manager.add_category(
            name=category.name,
            folder_name=category.foldername
        )
    
    return categories 