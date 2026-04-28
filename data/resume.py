"""
storage/resume.py — persistence for session state across sleep/wake cycles.

resume_sessions.json is written whenever the active session set changes and
read whenever a system wake is detected.  This guarantees that tunnels are
restored even if in-memory state was partially cleared before the wake handler
fires.
"""
import json
import logging
from typing import List, Dict

from config.paths import get_data_dir

logger = logging.getLogger(__name__)


def _resume_file():
    return get_data_dir() / 'resume_sessions.json'


def save_resume_state(sessions: List[Dict]) -> None:
    """Persist the list of active session dicts to disk."""
    try:
        with open(_resume_file(), 'w') as fh:
            json.dump(sessions, fh, indent=2)
        logger.debug("Resume state saved: %d session(s)", len(sessions))
    except Exception as exc:
        logger.error("Failed to save resume state: %s", exc)


def load_resume_state() -> List[Dict]:
    """Return the persisted session list, or [] if none exists."""
    try:
        f = _resume_file()
        if f.exists():
            with open(f, 'r') as fh:
                return json.load(fh)
    except Exception as exc:
        logger.error("Failed to load resume state: %s", exc)
    return []


def clear_resume_state() -> None:
    """Delete the resume file (called after a deliberate Stop All)."""
    try:
        _resume_file().unlink(missing_ok=True)
        logger.debug("Resume state cleared")
    except Exception as exc:
        logger.error("Failed to clear resume state: %s", exc)
