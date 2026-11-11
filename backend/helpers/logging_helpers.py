import logging
import os
import stat
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
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    log_dir = (directory or Path(user_log_dir(app_name))).absolute()
    log_file = log_dir / filename
    if log_dir.resolve() != log_dir:
        logger.warning("Skipping log output in linked directory %s", log_dir)
        return
    for path in (log_file, log_file.with_name(f"{log_file.name}.1")):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.resolve() != path:
            logger.warning("Skipping log output because %s is not a standalone file", path)
            return
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
