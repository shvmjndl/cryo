"""Structured logging for CRYO — everything gets logged."""

import logging
import sys
from datetime import datetime, timezone


class CryoFormatter(logging.Formatter):
    """Compact structured log format with timestamp, level, module, message."""

    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[35m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        color = self.COLORS.get(record.levelname, "")
        level = record.levelname[0]  # D/I/W/E/C
        module = record.name.replace("cryo.", "").replace("api.", "")[:20]
        msg = record.getMessage()

        # Include exception info if present
        exc = ""
        if record.exc_info and record.exc_info[1]:
            exc = f" | {record.exc_info[0].__name__}: {record.exc_info[1]}"

        return f"{color}{ts} {level} [{module:>20}]{self.RESET} {msg}{exc}"


def setup_logging(level: str = "INFO"):
    """Configure logging for all CRYO modules."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CryoFormatter())
    root.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    # Ensure CRYO loggers are at desired level
    for name in ["cryo", "cryo.literature", "cryo.protein", "cryo.drug",
                  "cryo.variant", "cryo.reports", "cryo.vlm", "cryo.bridge"]:
        logging.getLogger(name).setLevel(getattr(logging, level.upper(), logging.INFO))

    logging.getLogger("cryo").info("CRYO logging initialized (level=%s)", level)
