# Email Filter

A Python application for filtering and processing emails, with OpenAI GPT-4o-mini powered categorization and IMAP integration.

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
git clone https://github.com/yourusername/emailfilter.git
cd emailfilter

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
git clone https://github.com/yourusername/emailfilter.git
cd emailfilter

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
emailfilter daemon --config config.yaml

# Alternatively, use the imap command with the --daemon flag
emailfilter imap --config config.yaml --daemon
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
emailfilter imap --config config.yaml

# Process emails from a specific account
emailfilter imap --config config.yaml --account "Personal Gmail"

# Process emails from a specific folder
emailfilter imap --config config.yaml --account "Work Email" --folder "Important"

# Dry run (categorize but don't move emails)
emailfilter imap --config config.yaml --dry-run
```

### Basic Filtering

```python
from emailfilter import filter

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
from emailfilter import categorizer
from emailfilter.models import EmailAccount, EmailCategory

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
emailfilter filter --input emails.json --filter "from:example.com" --output filtered.json

# Categorize emails using OpenAI GPT-4o-mini
emailfilter categorize --input emails.json --category inbox --output important_emails.json

# Categorize all emails into their respective categories
emailfilter categorize --input emails.json --category all --output categorized.json
```

## Local State System

The application uses a local state system to track which emails have been processed, eliminating the need to modify emails by adding flags or labels. This approach has several benefits:

- **Non-intrusive**: Emails in your mailbox remain unchanged
- **Persistent**: The state is maintained between application restarts
- **Portable**: The state can be backed up and restored easily
- **Manageable**: You can view, clean, and reset the state as needed
- **Scalable**: Uses SQLite database for efficient storage and retrieval

### How It Works

The local state system stores a unique identifier for each processed email in a SQLite database located at `~/.emailfilter/processed_emails.db`. This identifier is generated based on the email's account, message ID, sender, subject, and date.

When the application processes emails, it checks this database to determine which emails have already been processed, ensuring that each email is only processed once. The SQLite database provides better performance and data integrity compared to the previous JSON-based approach, especially when dealing with large numbers of emails.

### Docker Persistence

When running in Docker, the SQLite database is stored at `/home/emailfilter/.emailfilter/processed_emails.db` and is automatically persisted through the `emailfilter_data` volume defined in the `docker-compose.yml` file. This ensures that your processed email state is maintained even if the container is restarted or recreated.

The application uses the `EMAILFILTER_STATE_DIR` environment variable to determine where to store the state database. This is set to `/home/emailfilter/.emailfilter` in the Dockerfile.

### Managing the State

You can manage the local state using the CLI:

```bash
# View the current state
python -m emailfilter.cli state view

# View state for a specific account
python -m emailfilter.cli state view --account "Personal Gmail"

# Clean up the state (removes entries older than 30 days)
python -m emailfilter.cli state clean

# Reset the state for all accounts (will cause all emails to be reprocessed)
python -m emailfilter.cli state reset

# Reset the state for a specific account
python -m emailfilter.cli state reset --account "Personal Gmail"
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

```yaml
# OpenAI API Key
openai_api_key: "your_openai_api_key"

# Email Accounts
accounts:
  - name: "Personal Gmail"
    email: "your.email@gmail.com"
    password: "your_app_password_here" # Use app password for Gmail
    imap_server: "imap.gmail.com"
    imap_port: 993
    ssl: true
    folders:
      - "INBOX"

# Processing Options
options:
  # Where to move emails after categorization
  move_emails: true

  # Folder names for each category
  category_folders:
    spam: "[Spam]"
    receipts: "[Receipts]"
    promotions: "[Promotions]"
    updates: "[Updates]"
    inbox: "INBOX" # Keep important emails in inbox

  # Daemon mode options
  idle_timeout: 1740 # IMAP IDLE timeout in seconds (29 minutes)
  reconnect_delay: 5 # Delay before reconnecting after an error
```

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
sudo nano /etc/systemd/system/emailfilter.service
```

Add the following content:

```ini
[Unit]
Description=Email Filter Daemon
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/emailfilter
ExecStart=/path/to/emailfilter/.venv/bin/emailfilter daemon --config /path/to/emailfilter/config.yaml
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable emailfilter
sudo systemctl start emailfilter
sudo systemctl status emailfilter
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
  emailfilter:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: emailfilter
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
docker build -t emailfilter .

# Run in interactive mode
docker run -it --rm -v $(pwd)/config:/config emailfilter imap --config /config/config.yaml --dry-run

# Run tests in the container
docker run -it --rm emailfilter pytest
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
from emailfilter import categorizer
categorizer.load_api_key("config.yaml")
category = categorizer.categorize_email(email)

# New code
from emailfilter import categorizer
from emailfilter.models import EmailAccount, EmailCategory

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
