# Mailmind

An AI-powered email management and categorization tool.

## Features

- Categorize emails using a trained model into:
  - SPAM: Unwanted or malicious emails
  - RECEIPTS: Purchase confirmations and receipts
  - PROMOTIONS: Marketing and promotional emails
  - UPDATES: Updates and notifications
  - INBOX: Important emails that need attention
- Automatic email organization with IMAP folder management
- Real-time email monitoring with IMAP IDLE support
- Configurable batch processing and rate limiting
- Local state tracking to avoid reprocessing emails
- Detailed logging and error handling

## Installation

### Using pip

```bash
pip install mailmind
```

### From source

```bash
git clone https://github.com/tomfagerland/mailmind.git
cd mailmind
pip install -e .
```

## Configuration

1. Create a configuration file:

```bash
cp config/config.yaml.example config/config.yaml
```

2. Edit `config/config.yaml` and add your email accounts:

```yaml
accounts:
  - name: "Your Account"
    email: "your.email@example.com"
    password: "your_app_password"
    imap_server: "imap.example.com"
    imap_port: 993
    ssl: true
    source_folder: "INBOX"
    categories:
      - name: "SPAM"
        description: "Unwanted or malicious emails"
        folder: "Spam"
      - name: "RECEIPTS"
        description: "Purchase confirmations and receipts"
        folder: "@Receipts"
      - name: "PROMOTIONS"
        description: "Marketing and promotional emails"
        folder: "@Promotions"
      - name: "UPDATES"
        description: "Updates and notifications"
        folder: "@Updates"
      - name: "INBOX"
        description: "Important emails that need attention"
        folder: "INBOX"

options:
  max_emails: 100
  batch_size: 10
  idle_timeout: 1740
  reconnect_delay: 5
```

## Usage

### Command Line

```bash
# Run in inference mode
mailmind --config config/config.yaml

# Run in training mode
mailmind-train --config config/config.yaml
```

### Python API

```python
from mailmind.inference.categorizer import initialize_categorizer, batch_categorize_emails_for_account
from mailmind.inference.models import Account, Category

# Initialize the categorizer
initialize_categorizer()

# Create an account with categories
account = Account(
    name="Test Account",
    email_address="test@example.com",
    password="password",
    imap_server="imap.example.com",
    categories=[
        Category("SPAM", "Unwanted emails", "Spam"),
        Category("RECEIPTS", "Order confirmations", "Receipts"),
        Category("PROMOTIONS", "Marketing emails", "Promotions"),
        Category("UPDATES", "Notifications", "Updates"),
        Category("INBOX", "Important emails", "INBOX")
    ]
)

# Categorize emails
emails = [
    {
        "subject": "Order Confirmation",
        "from": "store@example.com",
        "to": "you@example.com",
        "date": "2024-03-19T10:00:00Z",
        "body": "Thank you for your order..."
    }
]

results = batch_categorize_emails_for_account(emails, account)
for result in results:
    print(f"Category: {result['category']}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Reasoning: {result['reasoning']}")
```

## Development

### Setup

1. Clone the repository:

```bash
git clone https://github.com/tomfagerland/mailmind.git
cd mailmind
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:

```bash
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Style

```bash
# Format code
black .
isort .

# Type checking
mypy .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
