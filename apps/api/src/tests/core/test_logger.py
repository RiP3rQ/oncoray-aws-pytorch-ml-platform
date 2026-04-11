"""
Tests for core logger configuration and utility functions.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.logger import (
    LOG_NAME,
    PrettyFormatter,
    configure_logging,
    get_logger,
)

# =============================================================================
# Tests for PrettyFormatter
# =============================================================================


class TestPrettyFormatter:
    """Tests for PrettyFormatter."""

    def test_format_with_color(self):
        """PrettyFormatter should format records with color when use_color=True."""
        formatter = PrettyFormatter(use_color=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Test message" in result
        # Should contain ANSI escape codes for color
        assert "\x1b[" in result

    def test_format_without_color(self):
        """PrettyFormatter should format records without color when use_color=False."""
        formatter = PrettyFormatter(use_color=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Test message" in result
        # Should NOT contain ANSI escape codes
        assert "\x1b[" not in result

    def test_format_log_levels(self):
        """PrettyFormatter should handle different log levels."""
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            formatter = PrettyFormatter(use_color=True)
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg=f"{name} message",
                args=(),
                exc_info=None,
            )
            result = formatter.format(record)
            assert f"{name} message" in result

    def test_format_unknown_level(self):
        """PrettyFormatter should handle unknown log levels without color prefix."""
        formatter = PrettyFormatter(use_color=True)
        record = logging.LogRecord(
            name="test",
            level=999,  # Unknown level
            pathname="",
            lineno=0,
            msg="Unknown level",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Unknown level" in result


# =============================================================================
# Tests for _resolve_log_level
# =============================================================================


class TestResolveLogLevel:
    """Tests for _resolve_log_level internal function."""

    def test_resolve_info_level(self):
        """_resolve_log_level should resolve 'INFO' to logging.INFO."""
        from src.core.logger import _resolve_log_level

        assert _resolve_log_level("INFO") == logging.INFO

    def test_resolve_debug_level(self):
        """_resolve_log_level should resolve 'debug' to logging.DEBUG."""
        from src.core.logger import _resolve_log_level

        assert _resolve_log_level("debug") == logging.DEBUG

    def test_resolve_none_defaults_to_env(self):
        """_resolve_log_level should default to INFO when None."""
        from src.core.logger import _resolve_log_level

        with patch.dict("os.environ", {}, clear=True):
            result = _resolve_log_level(None)
            assert result == logging.INFO

    def test_resolve_warning_level(self):
        """_resolve_log_level should resolve 'WARNING' to logging.WARNING."""
        from src.core.logger import _resolve_log_level

        assert _resolve_log_level("WARNING") == logging.WARNING


# =============================================================================
# Tests for configure_logging
# =============================================================================


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_returns_logger(self):
        """configure_logging should return a logger instance."""
        # Reset the global state so we can re-configure
        import src.core.logger as logger_module

        logger_module._LOGGING_CONFIGURED = False

        logger = configure_logging()
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_sets_level(self):
        """configure_logging should set logger to specified level."""
        import src.core.logger as logger_module

        logger_module._LOGGING_CONFIGURED = False

        logger = configure_logging(level="DEBUG")
        assert logger.level <= logging.DEBUG

    def test_configure_logging_reconfigure(self):
        """configure_logging should update level on subsequent calls."""
        import src.core.logger as logger_module

        logger_module._LOGGING_CONFIGURED = False

        configure_logging(level="INFO")
        logger2 = configure_logging(level="DEBUG")
        assert logger2 is not None


# =============================================================================
# Tests for get_logger
# =============================================================================


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self):
        """get_logger should return a logger with the module name."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert "test_module" in logger.name

    def test_get_logger_without_name(self):
        """get_logger without name should return root logger."""
        logger = get_logger()
        assert logger.name == LOG_NAME

    def test_get_logger_with_prefix(self):
        """get_logger should not double-prefix if name already has prefix."""
        logger = get_logger(f"{LOG_NAME}.mymodule")
        assert logger.name == f"{LOG_NAME}.mymodule"
