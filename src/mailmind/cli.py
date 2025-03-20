"""Command-line interface for mailmind."""

import sys
import logging
from mailmind.email_processor import main as email_processor_main

# Version information
__version__ = "1.0.0"

def main():
    """Main entry point for the CLI."""
    if '--version' in sys.argv:
        print(f'mailmind {__version__}')
        sys.exit(0)

    config_path = "/config/config.yaml"  # default
    daemon_mode = False

    # Simple arg parsing
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--config' and i < len(sys.argv):
            config_path = sys.argv[i + 1]
        elif arg == '--daemon':
            daemon_mode = True

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    try:
        email_processor_main(config_path, daemon_mode=daemon_mode)
    except Exception as e:
        logging.error(f"Error processing emails: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 