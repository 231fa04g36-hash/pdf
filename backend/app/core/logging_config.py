import logging
import sys
from typing import Any

class SensitiveFilter(logging.Filter):
    """
    Filter to redact sensitive details like API keys or passwords.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        # Prevent logging of sensitive strings in the log messages
        try:
            msg = record.getMessage()
        except Exception as e:
            # Fallback if formatting fails (e.g. invalid arguments passed to logger format string)
            msg = str(record.msg)
            # Rewrite message and clear args to prevent downstream handlers from failing and printing tracebacks
            record.msg = f"[Formatting Error in Log: {msg}] - Error: {e}"
            record.args = ()

        sensitive_keywords = ["password", "secret", "token", "api_key", "apikey", "bearer"]
        for key in sensitive_keywords:
            if key in msg.lower():
                # Simple redaction logic
                record.msg = f"[REDACTED LOG: Contains reference to sensitive keyword '{key}']"
                record.args = ()
                break
        return True

def setup_logging(log_level_name: str = "INFO") -> None:
    # Map string level to logging level
    level = getattr(logging, log_level_name.upper(), logging.INFO)

    # Root Logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Define standard format
    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler using stdout (per requirement)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.addFilter(SensitiveFilter())

    root_logger.addHandler(console_handler)

    # OLD: Set only uvicorn library loggers to be less noisy
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    
    # NEW: Silence extremely verbose third-party loggers (like pdfminer, pdfplumber, chromadb, etc.)
    # to prevent millions of debug logging lines and TypeError formatting tracebacks during PDF uploads.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info("Logging successfully initialized.")
