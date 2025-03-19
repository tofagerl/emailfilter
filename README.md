# Mailmind

An AI-powered email management and categorization tool using OpenAI's GPT-4o-mini.

## Features

- Filter emails based on custom criteria
- Categorize emails using OpenAI's GPT-4o-mini API into:
  - Spam: Unwanted, unsolicited emails that might be scams or junk
  - Receipts: Transaction confirmations, receipts, order updates
  - Promotions: Marketing emails, newsletters, offers, discounts
  - Updates: Non-urgent notifications, social media updates, news
  - Inbox: Important emails that need attention or quick response
- IMAP integration to process emails directly from your accounts
- Automatic organization of emails into appropriate folders
- Non-intrusive local state system to track processed emails
- Real-time email monitoring using IMAP IDLE for push notifications
- Command-line interface for easy integration
- Batch processing to handle large email volumes
- Docker support for easy deployment and containerization

## Installation

### Standard Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone https://github.com/yourusername/mailmind.git
cd mailmind

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Set up your configuration
cp config.yaml.example config.yaml
# Edit config.yaml and add your email accounts and OpenAI API key
```

### Docker Installation

You can also run the application using Docker:

```bash
# Clone the repository
git clone https://github.com/yourusername/mailmind.git
cd mailmind

# Create and customize your configuration
cp config/config.yaml.docker config/config.yaml
# Edit config/config.yaml and add your email accounts and OpenAI API key

# Build and run with Docker Compose
docker-compose up -d
```

## Usage

### Continuous Email Monitoring (Daemon Mode)

The most powerful way to use this application is to run it as a daemon that continuously monitors your email accounts and processes new emails as they arrive:

```bash
# Run as a daemon service
mailmind daemon --config config.yaml

# Alternatively, use the imap command with the --daemon flag
mailmind imap --config config.yaml --daemon
```

In daemon mode, the application:

- Connects to all configured email accounts
- Processes any existing unprocessed emails
- Listens for new emails using IMAP IDLE (push notifications)
- Automatically categorizes and organizes new emails as they arrive
- Reconnects automatically if the connection is lost

### One-time IMAP Processing

If you prefer to process emails on-demand rather than continuously:

```bash
# Process emails from all accounts in your configuration
mailmind imap --config config.yaml

# Process emails from a specific account
mailmind imap --config config.yaml --account "Personal Gmail"

# Process emails from a specific folder
mailmind imap --config config.yaml --account "Work Email" --folder "Important"

# Dry run (categorize but don't move emails)
mailmind imap --config config.yaml --dry-run
```

### Basic Filtering

```python
from mailmind import filter

# Example usage
emails = [
    {"from": "user@example.com", "subject": "Hello", "body": "Test message"},
    {"from": "spam@test.com", "subject": "Win money", "body": "Click here"},
]

# Filter emails from example.com
filtered = filter.filter_emails(emails, {"from": "example.com"})
```

### OpenAI GPT-4o-mini powered Categorization

```python
from mailmind import categorizer
from mailmind.models import EmailAccount, EmailCategory

# Initialize the OpenAI client
categorizer.initialize_openai_client(api_key="your_openai_api_key")
# Or initialize from a config file
# categorizer.initialize_openai_client(config_path="config.yaml")

# Create an account with categories
account = EmailAccount(
    name="Personal",
    email="user@example.com",
    password="password",
    imap_server="imap.example.com",
    categories=[
        EmailCategory(name="SPAM", description="Unwanted emails", foldername="[Spam]"),
        EmailCategory(name="RECEIPTS", description="Order confirmations", foldername="[Receipts]"),
        EmailCategory(name="INBOX", description="Important emails", foldername="INBOX")
    ]
)

# Batch categorize emails for a specific account
emails = [
    {
        "from": "shop@example.com",
        "to": "user@gmail.com",
        "subject": "Your order has shipped",
        "body": "Your recent order #12345 has shipped and will arrive tomorrow."
    }
]

results = categorizer.batch_categorize_emails_for_account(emails, account)
print(f"Email category: {results[0]['category']}")  # Likely "RECEIPTS"
```

### Command Line Interface

```bash
# Basic filtering
mailmind filter --input emails.json --filter "from:example.com" --output filtered.json

# Categorize emails using OpenAI GPT-4o-mini
mailmind categorize --input emails.json --category inbox --output important_emails.json

# Categorize all emails into their respective categories
mailmind categorize --input emails.json --category all --output categorized.json
```

## Local State System

The application uses a local state system to track which emails have been processed, eliminating the need to modify emails by adding flags or labels. This approach has several benefits:

- **Non-intrusive**: Emails in your mailbox remain unchanged
- **Persistent**: The state is maintained between application restarts
- **Portable**: The state can be backed up and restored easily
- **Manageable**: You can view, clean, and reset the state as needed
- **Scalable**: Uses SQLite database for efficient storage and retrieval

### How It Works

The local state system stores a unique identifier for each processed email in a SQLite database located at `~/.mailmind/processed_emails.db`. This identifier is generated based on the email's account, message ID, sender, subject, and date.

When the application processes emails, it checks this database to determine which emails have already been processed, ensuring that each email is only processed once. The SQLite database provides better performance and data integrity compared to the previous JSON-based approach, especially when dealing with large numbers of emails.

### Docker Persistence

When running in Docker, the SQLite database is stored at `/home/mailmind/.mailmind/processed_emails.db` and is automatically persisted through the `mailmind_data` volume defined in the `docker-compose.yml` file. This ensures that your processed email state is maintained even if the container is restarted or recreated.

The application uses the `MAILMIND_STATE_DIR` environment variable to determine where to store the state database. This is set to `/home/mailmind/.mailmind` in the Dockerfile.

### Managing the State

You can manage the local state using the CLI:

```bash
# View the current state
python -m mailmind.cli state view

# View state for a specific account
python -m mailmind.cli state view --account "Personal Gmail"

# Clean up the state (removes entries older than 30 days)
python -m mailmind.cli state clean

# Reset the state for all accounts (will cause all emails to be reprocessed)
python -m mailmind.cli state reset

# Reset the state for a specific account
python -m mailmind.cli state reset --account "Personal Gmail"
```

### Testing the State System

A test script is provided to help you understand and test the local state system:

```bash
# View the current state
./test_local_state.py --action view

# Add test emails to the state
./test_local_state.py --action add --account "Test Account" --count 10

# Clean up the state
./test_local_state.py --action clean

# Reset the state
./test_local_state.py --action reset
```

## Configuration

The application uses a YAML configuration file for IMAP accounts and processing options:

````yaml
# OpenAI API Key
openai_api_key: "your_openai_api_key_here"

# AI Model Configuration
# The application uses GPT-4o mini for email categorization
# This provides better accuracy than GPT-3.5-turbo while being more cost-effective than GPT-4

# Email Accounts
accounts:
  - name: "Personal Gmail"
    email: "your.email@gmail.com"
    password: "your_app_password_here"  # Use app password for Gmail
    imap_server: "imap.gmail.com"
    imap_port: 993
    ssl: true
    folders:
      - "INBOX"
    # Per-account categories
    categories:
      - name: "SPAM"
        description: "Unwanted or malicious emails"
        foldername: "[Spam]"
      - name: "RECEIPTS"
        description: "Purchase confirmations and receipts"
        foldername: "[Receipts]"
      - name: "PROMOTIONS"
        description: "Marketing and promotional emails"
        foldername: "[Promotions]"
      - name: "UPDATES"
        description: "Updates and notifications"
        foldername: "[Updates]"
      - name: "INBOX"
        description: "Important emails that need attention"
        foldername: "INBOX"
      - name: "PERSONAL"
        description: "Personal communications from friends and family"
        foldername: "[Personal]"

  - name: "Work Email"
    email: "your.work@example.com"
    password: "your_password_here"
    imap_server: "imap.example.com"
    imap_port: 993
    ssl: true
    folders:
      - "INBOX"
      - "Important"
    # Different categories for work email
    categories:
      - name: "SPAM"
        description: "Unwanted or malicious emails"
        foldername: "Junk"
      - name: "CLIENTS"
        description: "Emails from clients or about client projects"
        foldername: "Clients"
      - name: "INTERNAL"
        description: "Internal company communications"
        foldername: "Internal"
      - name: "PROJECTS"
        description: "Project-related emails"
        foldername: "Projects"
      - name: "MEETINGS"
        description: "Meeting invitations and updates"
        foldername: "Meetings"
      - name: "INBOX"
        description: "Important emails that need immediate attention"
        foldername: "INBOX"

# Processing Options
options:
  # Where to move emails after categorization
  move_emails: true

  # AI model to use for categorization
  # Options: "gpt-4o-mini" (default), "gpt-3.5-turbo", "gpt-4", "gpt-4o"
  model: "gpt-4o-mini"

  # Maximum number of emails to process per run
  max_emails_per_run: 100

  # Batch size for API calls
  batch_size: 10

  # Daemon mode options

  # IMAP IDLE timeout in seconds (default: 29 minutes)
  # Most servers disconnect after 30 minutes of inactivity
  idle_timeout: 1740

  # Delay in seconds before reconnecting after an error
  reconnect_delay: 5

# Local State System
# The application now uses a local state system to track processed emails
# instead of adding flags to emails. This state is stored in:
# ~/.mailmind/processed_emails.db
#
# You can manage this state using the CLI:
# - View state: python -m mailmind.cli state view
# - Clean state: python -m mailmind.cli state clean
# - Reset state: python -m mailmind.cli state reset

## Non-Intrusive Operation

The application is designed to be non-intrusive and will not modify your emails in any way:

- No flags or labels are added to emails
- No read/unread status is changed
- No email content is modified
- Only folder moves are performed (if configured)

The application uses a local state system to track which emails have been processed, ensuring that each email is only processed once without modifying the emails themselves.

## Running as a Service

### Using systemd (Linux)

To run the application as a background service on Linux, you can create a systemd service:

```bash
# Create a systemd service file
sudo nano /etc/systemd/system/mailmind.service
````

Add the following content:

```ini
[Unit]
Description=Mailmind Daemon
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/mailmind
ExecStart=/path/to/mailmind/.venv/bin/mailmind daemon --config /path/to/mailmind/config.yaml
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable mailmind
sudo systemctl start mailmind
sudo systemctl status mailmind
```

### Using Docker

The easiest way to run the application as a service is using Docker:

```bash
# Start the container in the background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

To customize the Docker configuration, edit the `docker-compose.yml` file:

```yaml
version: "3.8"

services:
  mailmind:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mailmind
    restart: unless-stopped
    volumes:
      - ./config:/config
    # Uncomment to run in one-time processing mode instead of daemon mode
    # command: ["imap", "--config", "/config/config.yaml"]
```

## Development

```bash
# Run tests
pytest

# Format code
black .
isort .

# Type checking
mypy src/
```

## Docker Development

For development with Docker:

```bash
# Build the image
docker build -t mailmind .

# Run in interactive mode
docker run -it --rm -v $(pwd)/config:/config mailmind imap --config /config/config.yaml --dry-run

# Run tests in the container
docker run -it --rm mailmind pytest
```

## Note on API Usage

This application uses OpenAI's GPT-4o-mini model, which provides a good balance between quality and cost for email categorization. It's more efficient than GPT-4 while still delivering accurate results for this specific task.

When running in daemon mode, the application will make API calls whenever new emails arrive, so be mindful of your API usage and costs.

## API Changes and Deprecations

The codebase has undergone significant improvements to enhance maintainability and performance. As a result, some older APIs have been deprecated:

### Deprecated Modules

- **`imap_client.py`**: This module is deprecated and will be removed in a future version. Use `email_processor.py` instead, which provides a more robust implementation with better error handling and configuration options.

### Deprecated Functions

The following functions in `categorizer.py` have been removed:

- **`load_api_key()`**: Replaced by `initialize_openai_client()`
- **`set_api_key()`**: Replaced by `initialize_openai_client()`
- **`categorize_email()`**: Replaced by `batch_categorize_emails_for_account()`
- **`batch_categorize_emails()`**: Replaced by `batch_categorize_emails_for_account()`
- **`categorize_and_filter()`**: Replaced by `batch_categorize_emails_for_account()` with per-account categories

### New APIs

- **`initialize_openai_client(api_key=None, config_path=None)`**: Initialize the OpenAI client with an API key provided directly, from a config file, or from the environment variable `OPENAI_API_KEY`.
- **`batch_categorize_emails_for_account(emails, account, batch_size=10, model="gpt-4o-mini")`**: Categorize a batch of emails for a specific account, using the account's category definitions.

### Migration Guide

If you're using the deprecated functions, here's how to migrate to the new APIs:

```python
# Old code
from mailmind import categorizer
categorizer.load_api_key("config.yaml")
category = categorizer.categorize_email(email)

# New code
from mailmind import categorizer
from mailmind.models import EmailAccount, EmailCategory

# Initialize the client
categorizer.initialize_openai_client(config_path="config.yaml")

# Create an account with categories
account = EmailAccount(
    name="Personal",
    email="user@example.com",
    password="password",
    imap_server="imap.example.com",
    categories=[
        EmailCategory(name="SPAM", description="Unwanted emails", foldername="[Spam]"),
        EmailCategory(name="RECEIPTS", description="Order confirmations", foldername="[Receipts]"),
        EmailCategory(name="INBOX", description="Important emails", foldername="INBOX")
    ]
)

# Categorize emails
results = categorizer.batch_categorize_emails_for_account([email], account)
category = results[0]["category"]
```

## License

MIT
