import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir


def setup_logging(
    app_name: str,
    filename: str = "app.log",
    enable_logging: bool = True,
    log_level: int = logging.DEBUG,
    directory: Path | None = None,
) -> None:
    """Sets up logging configuration for the application. Outputs to both console and rotating file."""

    # Update root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Handler cleanup
    if logger.hasHandlers():
        logger.handlers.clear()

    # Avoid logging if disabled
    if not enable_logging:
        logger.addHandler(logging.NullHandler())
        return

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Log Absolute Path
    log_dir = str(directory) if directory is not None else user_log_dir(app_name)
    log_file_path = os.path.join(log_dir, filename)

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
