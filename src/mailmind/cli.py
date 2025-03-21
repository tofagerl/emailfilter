"""Command-line interface for mailmind."""

import sys
import logging
import os
from mailmind.email_processor import main as email_processor_main

# Version information
__version__ = "1.0.0"

def setup_logging():
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    log_dir = "/home/mailmind/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up file handler
    log_file = os.path.join(log_dir, "mailmind.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info(f"Logging to {log_file}")

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

    # Set up logging
    setup_logging()

    try:
        email_processor_main(config_path, daemon_mode=daemon_mode)
    except Exception as e:
        logging.error(f"Error processing emails: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 