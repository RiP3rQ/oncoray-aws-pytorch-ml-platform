import copy
import logging
import logging.config
import os
import sys

LOG_NAME = "core_api"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOGGING_CONFIGURED = False


class PrettyFormatter(logging.Formatter):
    """Formatter that keeps logs readable in local development."""

    COLORS = {
        logging.DEBUG: "\x1b[36m",
        logging.INFO: "\x1b[32m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[35m",
    }
    RESET = "\x1b[0m"

    def __init__(self, use_color: bool) -> None:
        super().__init__(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        formatted_record = copy.copy(record)
        level_name = formatted_record.levelname.ljust(8)

        if self.use_color:
            color = self.COLORS.get(formatted_record.levelno, "")
            if color:
                level_name = f"{color}{level_name}{self.RESET}"

        formatted_record.levelname = level_name
        return super().format(formatted_record)


def _resolve_log_level(level: str | None = None) -> int:
    raw_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    return getattr(logging, raw_level, logging.INFO)


def _resolve_log_level_name(level: str | None = None) -> str:
    return logging.getLevelName(_resolve_log_level(level))


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure shared logging for app and uvicorn, similar to the gist setup."""
    global _LOGGING_CONFIGURED

    resolved_level = _resolve_log_level_name(level)

    if not _LOGGING_CONFIGURED:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "()": PrettyFormatter,
                        "use_color": sys.stdout.isatty(),
                    }
                },
                "handlers": {
                    "default": {
                        "class": "logging.StreamHandler",
                        "formatter": "default",
                        "stream": "ext://sys.stdout",
                    }
                },
                "loggers": {
                    LOG_NAME: {
                        "level": resolved_level,
                        "handlers": ["default"],
                        "propagate": False,
                    },
                    "uvicorn": {
                        "level": resolved_level,
                        "handlers": ["default"],
                        "propagate": False,
                    },
                    "uvicorn.error": {
                        "level": resolved_level,
                        "handlers": ["default"],
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "level": resolved_level,
                        "handlers": ["default"],
                        "propagate": False,
                    },
                },
                "root": {
                    "level": resolved_level,
                    "handlers": ["default"],
                },
            }
        )
        _LOGGING_CONFIGURED = True
    else:
        for logger_name in (LOG_NAME, "uvicorn", "uvicorn.error", "uvicorn.access", ""):
            logging.getLogger(logger_name).setLevel(resolved_level)

    return logging.getLogger(LOG_NAME)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application logger scoped to the given module."""
    if not name:
        return logging.getLogger(LOG_NAME)

    if name.startswith(f"{LOG_NAME}."):
        return logging.getLogger(name)

    return logging.getLogger(f"{LOG_NAME}.{name}")
