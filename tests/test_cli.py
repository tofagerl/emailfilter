"""Unit tests for the CLI module."""

import os
import sys
import logging
import tempfile
from unittest import mock
import pytest
from mailmind.cli import setup_logging, main, __version__

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_setup_logging_with_custom_dir(temp_log_dir):
    """Test setup_logging with a custom log directory."""
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up logging
    setup_logging(temp_log_dir)
    
    # Verify log file was created
    log_file = os.path.join(temp_log_dir, "mailmind.log")
    assert os.path.exists(log_file)
    
    # Verify handlers were added
    assert len(root_logger.handlers) == 2  # File and console handlers
    
    # Test logging
    test_message = "Test log message"
    logging.info(test_message)
    
    # Verify message was written to file
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert test_message in log_content

def test_setup_logging_with_default_dir():
    """Test setup_logging with default directory."""
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up logging with default directory
    setup_logging()
    
    # Verify handlers were added
    assert len(root_logger.handlers) == 2  # File and console handlers

def test_main_version():
    """Test --version flag."""
    with mock.patch.object(sys, 'argv', ['mailmind', '--version']), \
         mock.patch('sys.exit') as mock_exit, \
         mock.patch('mailmind.cli.ConfigManager') as mock_config_manager:
        
        # Mock config manager to prevent error
        mock_config = mock.MagicMock()
        mock_config_manager.return_value = mock_config
        
        main()
        mock_exit.assert_called_once_with(0)

def test_main_with_config():
    """Test --config flag."""
    test_config = "/path/to/config.yaml"
    with mock.patch.object(sys, 'argv', ['mailmind', '--config', test_config]):
        with mock.patch('mailmind.cli.ConfigManager') as mock_config_manager, \
             mock.patch('mailmind.cli.IMAPManager') as mock_imap_manager, \
             mock.patch('mailmind.cli.SQLiteStateManager') as mock_state_manager, \
             mock.patch('mailmind.cli.EmailProcessor') as mock_email_processor:
            
            main()
            
            # Verify components were initialized
            mock_config_manager.assert_called_once_with(test_config)
            mock_imap_manager.assert_called_once()
            mock_state_manager.assert_called_once()
            mock_email_processor.assert_called_once()

def test_main_daemon_mode():
    """Test --daemon flag."""
    with mock.patch.object(sys, 'argv', ['mailmind', '--daemon']):
        with mock.patch('mailmind.cli.ConfigManager') as mock_config_manager, \
             mock.patch('mailmind.cli.IMAPManager') as mock_imap_manager, \
             mock.patch('mailmind.cli.SQLiteStateManager') as mock_state_manager, \
             mock.patch('mailmind.cli.EmailProcessor') as mock_email_processor:
            
            # Create mock instance
            mock_processor = mock.MagicMock()
            mock_email_processor.return_value = mock_processor
            
            main()
            
            # Verify start_monitoring was called
            mock_processor.start_monitoring.assert_called_once()

def test_main_with_log_dir():
    """Test --log-dir flag."""
    test_log_dir = "/path/to/logs"
    with mock.patch.object(sys, 'argv', ['mailmind', '--log-dir', test_log_dir]):
        with mock.patch('mailmind.cli.setup_logging') as mock_setup_logging, \
             mock.patch('mailmind.cli.ConfigManager') as mock_config_manager, \
             mock.patch('mailmind.cli.IMAPManager') as mock_imap_manager, \
             mock.patch('mailmind.cli.SQLiteStateManager') as mock_state_manager, \
             mock.patch('mailmind.cli.EmailProcessor') as mock_email_processor:
            
            main()
            
            # Verify setup_logging was called with correct directory
            mock_setup_logging.assert_called_once_with(test_log_dir)

def test_main_error_handling():
    """Test error handling in main function."""
    with mock.patch.object(sys, 'argv', ['mailmind']):
        with mock.patch('mailmind.cli.ConfigManager', side_effect=Exception("Test error")), \
             mock.patch('sys.exit') as mock_exit:
            
            main()
            
            # Verify sys.exit was called with error code 1
            mock_exit.assert_called_once_with(1) 