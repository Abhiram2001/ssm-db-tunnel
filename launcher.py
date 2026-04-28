"""
launcher.py — macOS entry point for SsmDbTunnel.

Responsibilities:
  1. Enforce single-instance via a PID lock file.
  2. Bootstrap the data directory (first-run hostname_port_map.json copy).
  3. Start the Flask server in a background daemon thread.
  4. Open the dashboard in the default browser once the server is ready.
  5. Run the rumps menu-bar app on the main thread (required by macOS Cocoa).
"""
import os
import sys
import signal
import threading
import time
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# Single-instance guard
# ---------------------------------------------------------------------------

def _pid_file() -> Path:
    from config.paths import get_data_dir
    return get_data_dir() / '.ssmtunnel.pid'


def _acquire_instance_lock() -> bool:
    """Write our PID to the lock file.  Return False if another instance is running."""
    pid_path = _pid_file()
    try:
        if pid_path.exists():
            old_pid = int(pid_path.read_text().strip())
            try:
                os.kill(old_pid, 0)   # signal 0 = existence check
                return False          # still alive
            except (ProcessLookupError, PermissionError):
                pass                  # stale PID — proceed
        pid_path.write_text(str(os.getpid()))
        return True
    except Exception:
        return True   # can't check → proceed


def _release_instance_lock() -> None:
    try:
        _pid_file().unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Flask server helpers
# ---------------------------------------------------------------------------

def _run_flask() -> None:
    from app import app
    from config.config import SERVER_HOST, SERVER_PORT
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)


def _wait_for_server(url: str, timeout: int = 20) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    from config.config import SERVER_URL
    from data.port_map import bootstrap_port_map
    from ui.menubar import SsmDbTunnelApp

    # Enforce single instance
    if not _acquire_instance_lock():
        webbrowser.open(SERVER_URL)
        sys.exit(0)

    # Bootstrap data directory on first run
    bootstrap_port_map()

    # Allow Ctrl-C to work cleanly in dev mode
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Start Flask in a background daemon thread
    flask_thread = threading.Thread(target=_run_flask, daemon=True, name='flask')
    flask_thread.start()

    # Open the browser as soon as the server is accepting connections
    def _open_when_ready() -> None:
        if _wait_for_server(SERVER_URL):
            webbrowser.open(SERVER_URL)

    threading.Thread(target=_open_when_ready, daemon=True, name='browser-opener').start()

    # Run the rumps menu-bar app on the main thread (Cocoa requirement)
    SsmDbTunnelApp().run()

    _release_instance_lock()


if __name__ == '__main__':
    main()
