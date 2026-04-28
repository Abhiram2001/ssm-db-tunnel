"""
storage/port_map.py — persistence for the hostname → local_port mapping.
"""
import json
import shutil
import logging
from typing import Dict

from config.config import HOSTNAME_PORT_MAP_FILE
from config.paths import get_bundle_dir

logger = logging.getLogger(__name__)


def load_hostname_port_map() -> Dict[str, int]:
    """Return the full hostname → local_port mapping; empty dict on error."""
    try:
        if HOSTNAME_PORT_MAP_FILE.exists():
            with open(HOSTNAME_PORT_MAP_FILE, 'r') as fh:
                return json.load(fh)
    except Exception as exc:
        logger.error("Error loading hostname port map: %s", exc)
    return {}


def save_hostname_port_map(mapping: Dict[str, int]) -> None:
    """Persist *mapping* to disk atomically (best-effort)."""
    try:
        with open(HOSTNAME_PORT_MAP_FILE, 'w') as fh:
            json.dump(mapping, fh, indent=2)
    except Exception as exc:
        logger.error("Error saving hostname port map: %s", exc)


def bootstrap_port_map() -> None:
    """Copy the bundled default hostname_port_map.json to the data dir if absent."""
    if HOSTNAME_PORT_MAP_FILE.exists():
        return
    bundled = get_bundle_dir() / 'data' / 'hostname_port_map.json'
    if bundled.exists():
        shutil.copy(bundled, HOSTNAME_PORT_MAP_FILE)
        logger.info("Bootstrapped hostname_port_map.json to %s", HOSTNAME_PORT_MAP_FILE)
