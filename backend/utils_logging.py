import logging
import os
from typing import Optional


def get_logger(name: str = __name__, run_id: Optional[int] = None, request_id: Optional[str] = None) -> logging.LoggerAdapter:
    logger = logging.getLogger(name)
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    # Avoid duplicate handlers in hot reload
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
    extra = {"run_id": run_id, "request_id": request_id}
    return logging.LoggerAdapter(logger, extra)


def kv(**kwargs) -> str:
    """Format key=value pairs for structured-ish logs."""
    parts = []
    for k, v in kwargs.items():
        try:
            parts.append(f"{k}={v}")
        except Exception:
            parts.append(f"{k}=<unrepr>")
    return " ".join(parts)
