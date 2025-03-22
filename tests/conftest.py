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
import time
from mailmind.imap_manager import IMAPManager
from imapclient.exceptions import IMAPClientError
import json
from mailmind.config import ConfigManager

class IMAPError(Exception):
    """Base class for IMAP errors."""
    pass

@pytest.fixture
def mock_config():
    """Create a mock configuration file for testing."""
    config = {
        'openai': {
            'api_key': 'test-key',
            'model': 'gpt-4',
            'temperature': 0.7,
            'max_tokens': 1000,
            'batch_size': 10
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
                    'name': 'INBOX',
                    'description': 'Default inbox',
                    'foldername': 'INBOX'
                },
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
            'min_samples_per_category': 3,
            'test_size': 0.2,
            'move_emails': True,
            'max_emails_per_run': 100,
            'idle_timeout': 300,
            'reconnect_delay': 5
        },
        'logging': {
            'level': 'DEBUG',
            'file': None,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        test_emails = {
            'Work': [
                ('Team meeting tomorrow', 'Reminder: Team meeting at 10am to discuss project deadlines.', 'WORK'),
                ('Project deadline', 'The project deadline is approaching, please submit your work.', 'WORK'),
                ('Weekly report', 'Please review the weekly progress report attached.', 'WORK'),
                ('Team sync', 'Let\'s sync up on the project status.', 'WORK'),
                ('Code review', 'Please review the code changes for the new feature.', 'WORK'),
                ('Sprint planning', 'Join us for sprint planning tomorrow.', 'WORK'),
                ('Team update', 'Here\'s the latest team update.', 'WORK'),
                ('Project milestone', 'We\'ve reached a major project milestone.', 'WORK'),
                ('Team feedback', 'Please provide feedback on the team performance.', 'WORK'),
                ('Work schedule', 'Updated work schedule for next week.', 'WORK')
            ],
            'Personal': [
                ('Family dinner', 'Are you coming to the family dinner on Sunday?', 'PERSONAL'),
                ('Weekend plans', 'What are your plans for the weekend? Want to have dinner?', 'PERSONAL'),
                ('Birthday party', "Don't forget about mom's birthday party next week.", 'PERSONAL'),
                ('Vacation plans', 'Let\'s plan our summer vacation.', 'PERSONAL'),
                ('Family reunion', 'Annual family reunion next month.', 'PERSONAL'),
                ('Personal update', 'Just wanted to share some personal news.', 'PERSONAL'),
                ('Holiday plans', 'Making plans for the holidays.', 'PERSONAL'),
                ('Friend meetup', 'Let\'s catch up over coffee.', 'PERSONAL'),
                ('Personal event', 'Reminder about the personal event.', 'PERSONAL'),
                ('Family photos', 'Sharing some family photos.', 'PERSONAL')
            ],
            'Shopping': [
                ('Order confirmation', 'Your order #12345 has been confirmed and will be shipped soon.', 'SHOPPING'),
                ('Shipping update', 'Your package has been shipped and will arrive tomorrow.', 'SHOPPING'),
                ('Order receipt', 'Thank you for your order. Here is your receipt.', 'SHOPPING'),
                ('New products', 'Check out our new products.', 'SHOPPING'),
                ('Order status', 'Your order status has been updated.', 'SHOPPING'),
                ('Shopping deals', 'Exclusive shopping deals for you.', 'SHOPPING'),
                ('Product review', 'Please review your recent purchase.', 'SHOPPING'),
                ('Shopping cart', 'Items left in your shopping cart.', 'SHOPPING'),
                ('Order delivered', 'Your order has been delivered.', 'SHOPPING'),
                ('Shopping discount', 'Special discount for your next purchase.', 'SHOPPING')
            ],
            'Travel': [
                ('Flight booking', 'Your flight has been booked for next month.', 'TRAVEL'),
                ('Hotel confirmation', 'Your hotel reservation is confirmed.', 'TRAVEL'),
                ('Travel itinerary', 'Here is your travel itinerary for the upcoming trip.', 'TRAVEL'),
                ('Flight update', 'Important update about your flight.', 'TRAVEL'),
                ('Travel plans', 'Finalizing travel plans for next week.', 'TRAVEL'),
                ('Hotel booking', 'New hotel booking confirmation.', 'TRAVEL'),
                ('Travel insurance', 'Your travel insurance details.', 'TRAVEL'),
                ('Trip reminder', 'Reminder about your upcoming trip.', 'TRAVEL'),
                ('Travel schedule', 'Updated travel schedule.', 'TRAVEL'),
                ('Travel documents', 'Important travel documents attached.', 'TRAVEL')
            ],
            'INBOX': [
                ('Order shipped', 'Your recent order has been shipped and will arrive soon.', 'SHOPPING'),
                ('Team deadline', 'Reminder about the upcoming team project deadline.', 'WORK'),
                ('Family gathering', 'Planning a family gathering next weekend.', 'PERSONAL'),
                ('Travel update', 'Update on your travel arrangements.', 'TRAVEL'),
                ('Shopping sale', 'Don\'t miss our biggest sale.', 'SHOPPING'),
                ('Work meeting', 'Important work meeting tomorrow.', 'WORK'),
                ('Personal event', 'Details about the personal event.', 'PERSONAL'),
                ('Flight change', 'Your flight schedule has changed.', 'TRAVEL'),
                ('Order status', 'Status update for your recent order.', 'SHOPPING'),
                ('Team update', 'Latest update from the team.', 'WORK')
            ]
        }

        for folder, emails in test_emails.items():
            self._folders[folder] = []
            for i, (subject, body, category) in enumerate(emails):
                self._folders[folder].append({
                    'id': f'{folder}_{i}',
                    'subject': subject,
                    'body': body,
                    'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000'),
                    'flags': [],
                    'folder': folder,
                    'category': category
                })

    def login(self, username, password):
        """Mock login."""
        if username != 'test@example.com' or password != 'test-pass':
            raise IMAPClientError('Invalid credentials')
        self._logged_in = True
        return True

    def logout(self):
        """Mock logout."""
        self._logged_in = False
        self._current_folder = None
        return True

    def select_folder(self, folder_name):
        """Mock folder selection."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if folder_name not in self._folders:
            raise IMAPClientError('Folder does not exist')
        self._current_folder = folder_name
        return True

    def list_folders(self, directory='""', pattern='*'):
        """Mock folder listing."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        return [(b'()', b'/', folder.encode()) for folder in self._folders.keys()]

    def search(self, criteria=None):
        """Mock email search."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._current_folder:
            raise IMAPClientError('No folder selected')
        return [email['id'] for email in self._folders[self._current_folder]]

    def fetch(self, message_set, message_parts):
        """Mock email fetching."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._current_folder:
            raise IMAPClientError('No folder selected')
        
        result = {}
        for msg_id in message_set:
            msg_id_str = msg_id if isinstance(msg_id, str) else msg_id.decode()
            email = next((e for e in self._folders[self._current_folder] if e['id'] == msg_id_str), None)
            if email:
                msg = MIMEText(email['body'])
                msg['Subject'] = email['subject']
                msg['Date'] = email['date']
                msg['Message-ID'] = email['id']
                msg['From'] = 'test@example.com'
                msg['To'] = 'test@example.com'
                msg['X-Folder'] = email['folder']
                msg_bytes = msg.as_bytes()
                result[msg_id] = {
                    b'RFC822': msg_bytes,
                    b'BODY.PEEK[]': msg_bytes,
                    b'FLAGS': email['flags'],
                    b'ENVELOPE': (
                        email['date'].encode(),
                        email['subject'].encode(),
                        (b'test@example.com',),
                        (b'test@example.com',),
                        None,
                        None,
                        None,
                        None,
                        None
                    ),
                    b'X-GM-LABELS': [email['category'].encode()] if email['category'] else []
                }
        return result

    def copy(self, message_set, new_folder):
        """Mock email copying."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._current_folder:
            raise IMAPClientError('No folder selected')
        if new_folder not in self._folders:
            raise IMAPClientError('Folder does not exist')
        
        for msg_id in message_set:
            email = next((e for e in self._folders[self._current_folder] if e['id'] == msg_id), None)
            if email:
                self._folders[new_folder].append(email.copy())
        return True

    def create_folder(self, folder_name):
        """Mock folder creation."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if folder_name in self._folders:
            raise IMAPClientError('Folder already exists')
        self._folders[folder_name] = []
        return True

    def noop(self):
        """Mock noop command."""
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        return True

class MockIMAPClient:
    def __init__(self, host, port=993, ssl=True):
        self._server = MockIMAPServer()
        self._logged_in = False
        self._host = host
        self._port = port
        self._ssl = ssl

    def login(self, username, password):
        if username != 'test@example.com' or password != 'test-pass':
            raise IMAPClientError('Invalid credentials')
        self._logged_in = True
        return True

    def logout(self):
        self._logged_in = False
        return True

    def select_folder(self, folder_name):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if folder_name not in self._server._folders:
            raise IMAPClientError('Folder does not exist')
        self._server._current_folder = folder_name
        return True

    def list_folders(self, directory='""', pattern='*'):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        return [(b'()', b'/', folder.encode()) for folder in self._server._folders.keys()]

    def search(self, criteria=None):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._server._current_folder:
            raise IMAPClientError('No folder selected')
        return [email['id'] for email in self._server._folders[self._server._current_folder]]

    def fetch(self, message_set, message_parts):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._server._current_folder:
            raise IMAPClientError('No folder selected')
        
        result = {}
        for msg_id in message_set:
            msg_id_str = msg_id if isinstance(msg_id, str) else msg_id.decode()
            email = next((e for e in self._server._folders[self._server._current_folder] if e['id'] == msg_id_str), None)
            if email:
                msg = MIMEText(email['body'])
                msg['Subject'] = email['subject']
                msg['Date'] = email['date']
                msg['Message-ID'] = email['id']
                msg['From'] = 'test@example.com'
                msg['To'] = 'test@example.com'
                msg['X-Folder'] = email['folder']
                msg_bytes = msg.as_bytes()
                result[msg_id] = {
                    b'RFC822': msg_bytes,
                    b'BODY.PEEK[]': msg_bytes,
                    b'FLAGS': email['flags'],
                    b'ENVELOPE': (
                        email['date'].encode(),
                        email['subject'].encode(),
                        (b'test@example.com',),
                        (b'test@example.com',),
                        None,
                        None,
                        None,
                        None,
                        None
                    ),
                    b'X-GM-LABELS': [email['category'].encode()] if email['category'] else []
                }
        return result

    def copy(self, message_set, new_folder):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if not self._server._current_folder:
            raise IMAPClientError('No folder selected')
        if new_folder not in self._server._folders:
            raise IMAPClientError('Folder does not exist')
        
        for msg_id in message_set:
            email = next((e for e in self._server._folders[self._server._current_folder] if e['id'] == msg_id), None)
            if email:
                self._server._folders[new_folder].append(email.copy())
        return True

    def create_folder(self, folder_name):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        if folder_name in self._server._folders:
            raise IMAPClientError('Folder already exists')
        self._server._folders[folder_name] = []
        return True

    def noop(self):
        if not self._logged_in:
            raise IMAPClientError('Not logged in')
        return True

@pytest.fixture(autouse=True)
def mock_imap(monkeypatch):
    """Create a mock IMAP server."""
    monkeypatch.setattr('mailmind.imap_manager.IMAPClient', MockIMAPClient)
    return MockIMAPServer()

@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI client for testing."""
    class MockOpenAI:
        def __init__(self, api_key=None):
            self.chat = MockChat()

    class MockChat:
        def completions(self):
            return self

        def create(self, messages, **kwargs):
            content = messages[-1]['content'].lower()
            if 'order' in content or 'shipped' in content or 'receipt' in content:
                category = 'SHOPPING'
            elif 'deadline' in content or 'meeting' in content or 'team' in content or 'project' in content:
                category = 'WORK'
            elif 'family' in content or 'dinner' in content or 'personal' in content:
                category = 'PERSONAL'
            elif 'flight' in content or 'hotel' in content or 'travel' in content:
                category = 'TRAVEL'
            else:
                category = 'INBOX'
                
            response = {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'category': category,
                            'confidence': 0.9,
                            'reasoning': f'Test reasoning for {category}'
                        })
                    }
                }]
            }
            return response

    monkeypatch.setattr('openai.OpenAI', MockOpenAI)
    return MockOpenAI()

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

@pytest.fixture
def mock_categorizer(mock_config, mock_openai):
    """Create a mock EmailCategorizer for testing."""
    from mailmind.categorizer import EmailCategorizer
    from mailmind.config_manager import ConfigManager
    
    config_manager = ConfigManager(mock_config)
    categorizer = EmailCategorizer(config_manager)
    categorizer.categories = [
        Category(name='SPAM', description='Spam emails', foldername='Spam'),
        Category(name='INBOX', description='Default inbox', foldername='INBOX'),
        Category(name='RECEIPTS', description='Receipt emails', foldername='Receipts')
    ]
    return categorizer 