"""
app.py — Application bootstrap and Flask instance.

This thin module:
  1. Augments PATH so GUI .app bundles find aws, lsof, etc.
  2. Configures logging (file + stdout).
  3. Bootstraps the hostname_port_map.json data file on first run.
  4. Starts the MySQL keep-alive background thread.
  5. Creates and exports the Flask application instance.

`launcher.py` imports `app` from here to run the development server.
`from app import app` also works inside PyInstaller frozen bundles.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from services.ssm import augment_path
from config.paths import get_log_dir
from data.port_map import bootstrap_port_map
from services.keepalive import start_keepalive
from api import create_app
from config.config import SERVER_HOST, SERVER_PORT

# ---------------------------------------------------------------------------
# PATH augmentation (must run before any subprocess calls)
# ---------------------------------------------------------------------------
augment_path()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _setup_logging() -> None:
    log_file = get_log_dir() / 'app.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[
            # Keep at most 5 × 1 MB files: app.log, app.log.1 … app.log.5
            RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # In the frozen .app there is no terminal; suppress Werkzeug's per-request
    # chatter (e.g. the /api/status poll every 5 s) so the log file stays clean.
    if getattr(sys, 'frozen', False):
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

_setup_logging()

# ---------------------------------------------------------------------------
# First-run bootstrap and background services
# ---------------------------------------------------------------------------
bootstrap_port_map()
start_keepalive()

# ---------------------------------------------------------------------------
# Flask application (importable as `from app import app`)
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)
