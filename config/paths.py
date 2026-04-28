"""
paths.py — shared path helpers for both app.py and launcher.py.

Single source of truth; no more copy-paste between the two entry points.
"""
import sys
from pathlib import Path


def get_bundle_dir() -> Path:
    """Read-only directory containing bundled resources (templates, default data).

    When frozen by PyInstaller this is sys._MEIPASS; otherwise the project root.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """User-writable directory for persistent data.

    ~/Library/Application Support/SsmDbTunnel when running as a .app bundle.
    Project root when running from source.
    """
    if getattr(sys, 'frozen', False):
        d = Path.home() / 'Library' / 'Application Support' / 'SsmDbTunnel'
    else:
        d = Path(__file__).parent.parent
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_dir() -> Path:
    """Directory for log files.

    ~/Library/Logs/SsmDbTunnel when running as a .app bundle.
    <project_root>/logs when running from source.
    """
    if getattr(sys, 'frozen', False):
        d = Path.home() / 'Library' / 'Logs' / 'SsmDbTunnel'
    else:
        d = get_data_dir() / 'logs'
    d.mkdir(parents=True, exist_ok=True)
    return d
