"""
storage/credentials.py — persistence for DB credentials used by the keep-alive thread.

The password is stored locally and is NEVER returned via the API.
"""
import json
import threading
import logging
from typing import Dict

from config.config import DB_CREDS_FILE

logger = logging.getLogger(__name__)

_creds_lock = threading.Lock()
_DEFAULT_CREDS: Dict[str, str] = {'user': '', 'password': '', 'database': 'mysql'}


def load_credentials() -> Dict[str, str]:
    """Return stored credentials merged with defaults; never raises."""
    try:
        with _creds_lock:
            if DB_CREDS_FILE.exists():
                with open(DB_CREDS_FILE, 'r') as fh:
                    stored = json.load(fh)
                return {**_DEFAULT_CREDS, **stored}
    except Exception as exc:
        logger.error("Error loading credentials: %s", exc)
    return dict(_DEFAULT_CREDS)


def save_credentials(creds: Dict[str, str]) -> None:
    """Persist *creds* to disk; never raises."""
    try:
        with _creds_lock:
            with open(DB_CREDS_FILE, 'w') as fh:
                json.dump(creds, fh, indent=2)
    except Exception as exc:
        logger.error("Error saving credentials: %s", exc)
