"""Command-line interface for mailmind."""

import sys

# Version information
__version__ = "1.0.0"

def main():
    """Main entry point for the CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == '--version':
        print(f'mailmind {__version__}')
        sys.exit(0)
    else:
        print(f'Usage: mailmind --version')
        sys.exit(1)

if __name__ == "__main__":
    main() 