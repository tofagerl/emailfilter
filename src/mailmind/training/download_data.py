"""CLI script for downloading training data from IMAP."""

import os
import logging
import click
import yaml
from pathlib import Path

from ..imap_downloader import IMAPDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise click.ClickException(f"Error loading config: {e}")

@click.command()
@click.option(
    '--config',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default='config.yaml',
    help='Path to config file'
)
@click.option(
    '--account',
    type=str,
    help='Account name from config to use (defaults to first account)'
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Directory to save downloaded emails'
)
@click.option(
    '--max-emails',
    type=int,
    default=100,
    help='Maximum number of emails to download per folder'
)
def download(
    config: Path,
    account: str,
    output_dir: Path,
    max_emails: int
):
    """Download emails from IMAP server for training data."""
    try:
        # Load config
        cfg = load_config(config)
        
        # Get account config
        accounts = cfg.get('accounts', [])
        if not accounts:
            raise click.ClickException("No accounts found in config")
        
        # Find requested account or use first
        acc_cfg = None
        if account:
            acc_cfg = next((a for a in accounts if a['name'] == account), None)
            if not acc_cfg:
                raise click.ClickException(f"Account {account} not found in config")
        else:
            acc_cfg = accounts[0]
            logger.info(f"Using first account: {acc_cfg['name']}")
        
        # Initialize downloader
        downloader = IMAPDownloader(
            host=acc_cfg['imap_server'],
            username=acc_cfg['email'],
            password=acc_cfg['password'],
            port=acc_cfg.get('imap_port', 993),
            use_ssl=acc_cfg.get('ssl', True),
            config_path=config
        )
        
        # Connect and list folders
        downloader.connect()
        folders = downloader.list_folders()
        logger.info(f"Available folders: {', '.join(folders)}")
        
        # Download emails
        downloader.download_emails(
            output_dir=output_dir,
            max_emails=max_emails
        )
        
        logger.info(f"Successfully downloaded emails to {output_dir}")
    except Exception as e:
        logger.error(f"Error downloading emails: {e}")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    download() 