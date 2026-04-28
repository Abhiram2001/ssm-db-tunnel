"""
config.py — all application constants and environment variable loading.
"""
import os
import socket
from dotenv import load_dotenv
from config.paths import get_data_dir

# ---------------------------------------------------------------------------
# Load .env — prefer the data-dir copy (production), fall back to CWD (dev)
# ---------------------------------------------------------------------------
_ENV_FILE = get_data_dir() / '.env'
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
else:
    load_dotenv()

# ---------------------------------------------------------------------------
# Flask server
# ---------------------------------------------------------------------------
SERVER_HOST = '127.0.0.1'


def _find_free_port(host: str = SERVER_HOST) -> int:
    """Ask the OS for a free port by binding to port 0.

    The OS allocates from the ephemeral range (49152–65535) — guaranteed free
    at the moment of the call and not used by any well-known service.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


SERVER_PORT: int = _find_free_port()
SERVER_URL = f'http://{SERVER_HOST}:{SERVER_PORT}'

# ---------------------------------------------------------------------------
# AWS SSM
# ---------------------------------------------------------------------------
SSM_TARGET = os.getenv('SSM_TARGET', 'i-0a47b5db6775690ff')
SSM_PROFILE = os.getenv('SSM_PROFILE', 'ssm')

# ---------------------------------------------------------------------------
# Port forwarding
# ---------------------------------------------------------------------------
FORWARD_BASE_PORT = 13300
KEEPALIVE_INTERVAL = 50  # seconds — below typical AWS idle-connection timeout

# ---------------------------------------------------------------------------
# Persistent file paths (resolved from the data directory)
# ---------------------------------------------------------------------------
HOSTNAME_PORT_MAP_FILE = get_data_dir() / 'hostname_port_map.json'
DB_CREDS_FILE = get_data_dir() / 'db_credentials.json'
