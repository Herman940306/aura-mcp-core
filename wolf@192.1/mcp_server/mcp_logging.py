"""MCP Logging Infrastructure

Centralized logging configuration for all MCP components.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class MCPLogger:
    """Centralized logging manager for MCP components."""

    # Log levels
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    # Default configuration
    DEFAULT_LOG_DIR = Path("logs")
    DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    DEFAULT_BACKUP_COUNT = 5

    _initialized = False
    _loggers = {}

    @classmethod
    def initialize(
        cls,
        log_dir: Optional[Path] = None,
        console_level: int = INFO,
        file_level: int = DEBUG,
        log_format: Optional[str] = None,
        date_format: Optional[str] = None,
    ) -> None:
        """Initialize logging infrastructure.

        Args:
            log_dir: Directory for log files
            console_level: Logging level for console output
            file_level: Logging level for file output
            log_format: Custom log format string
            date_format: Custom date format string
        """
        if cls._initialized:
            return

        # Set up log directory
        log_dir = log_dir or cls.DEFAULT_LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        # Set up formatters
        log_format = log_format or cls.DEFAULT_LOG_FORMAT
        date_format = date_format or cls.DEFAULT_DATE_FORMAT
        formatter = RedactingFormatter(log_format, date_format)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Main log file handler (rotating)
        main_log_file = log_dir / "mcp_main.log"
        file_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=cls.DEFAULT_MAX_BYTES,
            backupCount=cls.DEFAULT_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        cls._initialized = True

        # Log initialization
        root_logger.info("=" * 70)
        root_logger.info("MCP Logging Infrastructure Initialized")
        root_logger.info(f"Log Directory: {log_dir.absolute()}")
        root_logger.info(f"Console Level: {logging.getLevelName(console_level)}")
        root_logger.info(f"File Level: {logging.getLevelName(file_level)}")
        root_logger.info("=" * 70)

    @classmethod
    def get_logger(
        cls, name: str, log_file: Optional[str] = None, level: Optional[int] = None
    ) -> logging.Logger:
        """Get or create a logger for a specific component.

        Args:
            name: Logger name (usually module name)
            log_file: Optional separate log file for this component
            level: Optional logging level for this logger

        Returns:
            Configured logger instance
        """
        # Initialize if not already done
        if not cls._initialized:
            cls.initialize()

        # Return cached logger if exists
        if name in cls._loggers:
            return cls._loggers[name]

        # Create new logger
        logger = logging.getLogger(name)

        if level is not None:
            logger.setLevel(level)

        # Add component-specific file handler if requested
        if log_file:
            log_path = cls.DEFAULT_LOG_DIR / log_file
            handler = RotatingFileHandler(
                log_path,
                maxBytes=cls.DEFAULT_MAX_BYTES,
                backupCount=cls.DEFAULT_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setLevel(logging.DEBUG)
            formatter = RedactingFormatter(
                cls.DEFAULT_LOG_FORMAT, cls.DEFAULT_DATE_FORMAT
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Cache logger
        cls._loggers[name] = logger

        return logger

    @classmethod
    def log_operation(
        cls,
        logger: logging.Logger,
        operation: str,
        status: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log an operation with structured format.

        Args:
            logger: Logger instance
            operation: Operation name
            status: Operation status (SUCCESS, FAILED, WARNING)
            details: Optional additional details
        """
        message = f"[{operation}] {status}"
        if details:
            detail_str = " | ".join(f"{k}={v}" for k, v in details.items())
            message += f" | {detail_str}"

        if status == "SUCCESS":
            logger.info(message)
        elif status == "FAILED":
            logger.error(message)
        elif status == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    @classmethod
    def log_exception(
        cls, logger: logging.Logger, operation: str, exception: Exception
    ) -> None:
        """Log an exception with full traceback.

        Args:
            logger: Logger instance
            operation: Operation that failed
            exception: Exception that occurred
        """
        logger.error(
            f"[{operation}] EXCEPTION: {type(exception).__name__}: {str(exception)}",
            exc_info=True,
        )


SECRET_PATTERNS = [
    r"sk_live_[A-Za-z0-9]{8,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{12,}",
    r"aws_access_key=AKIA[0-9A-Z]{8,}",
    r"(?i)secret[_-]?key[:=][A-Za-z0-9/+]{16,}",
]


def _redact(text: str) -> str:
    for pat in SECRET_PATTERNS:

        def repl(m: re.Match) -> str:  # noqa: D401
            val = m.group(0)
            return val[:6] + "***" + val[-4:]

        text = re.sub(pat, repl, text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            try:
                # Safely redact formatted message result
                formatted = super().format(record)
                return _redact(formatted)
            except Exception:
                pass
        return super().format(record)


# Convenience functions for common logging patterns


def get_config_logger() -> logging.Logger:
    """Get logger for configuration operations."""
    return MCPLogger.get_logger("mcp.config", "config.log")


def get_sync_logger() -> logging.Logger:
    """Get logger for sync operations."""
    return MCPLogger.get_logger("mcp.sync", "sync.log")


def get_health_logger() -> logging.Logger:
    """Get logger for health check operations."""
    return MCPLogger.get_logger("mcp.health", "health.log")


def get_migration_logger() -> logging.Logger:
    """Get logger for migration operations."""
    return MCPLogger.get_logger("mcp.migration", "migration.log")


def get_backend_logger() -> logging.Logger:
    """Get logger for backend operations."""
    return MCPLogger.get_logger("mcp.backend", "backend.log")


# Initialize logging on module import
MCPLogger.initialize()


if __name__ == "__main__":
    # Test logging infrastructure
    print("Testing MCP Logging Infrastructure...")
    print()

    # Test different loggers
    config_logger = get_config_logger()
    sync_logger = get_sync_logger()
    health_logger = get_health_logger()

    # Test different log levels
    config_logger.debug("Debug message from config")
    config_logger.info("Info message from config")
    config_logger.warning("Warning message from config")
    config_logger.error("Error message from config")

    # Test structured logging
    MCPLogger.log_operation(
        sync_logger, "FILE_SYNC", "SUCCESS", {"files": 238, "duration": "4.38s"}
    )

    MCPLogger.log_operation(
        health_logger, "HEALTH_CHECK", "WARNING", {"passed": 6, "failed": 1}
    )

    # Test exception logging
    try:
        raise ValueError("Test exception")
    except Exception as e:
        MCPLogger.log_exception(config_logger, "TEST_OPERATION", e)

    print()
    print("✅ Logging infrastructure test complete")
    print(f"📁 Logs saved to: {MCPLogger.DEFAULT_LOG_DIR.absolute()}")
