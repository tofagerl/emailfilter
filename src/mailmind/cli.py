"""Command-line interface for mailmind."""

import logging
import sys
from mailmind.email_processor import main as email_processor_main

# Version information
__version__ = "1.0.0"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the CLI."""
    try:
        # Run the email processor in daemon mode
        email_processor_main("config.yaml", daemon_mode=True)
    except Exception as e:
        logger.error(f"Error processing emails: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 