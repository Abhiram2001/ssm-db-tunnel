"""
ui/menubar.py — macOS menu-bar application (rumps).

Provides a database-cylinder icon in the menu bar that:
  - Shows blue  (idle)   when no port-forwarding sessions are active.
  - Shows green (active) + session count badge when forwarding is live.

Menu items:
  Open Dashboard      — open the Flask dashboard in the default browser
  ──────────────────
  Sessions: N         — read-only session count display
  Stop All Sessions   — POST /api/stop
  ──────────────────
  Reveal Config Files — open data directory in Finder
  View Logs           — open the log file in the default editor
  ──────────────────
  Quit                — gracefully terminate all SSM sessions, then quit

Sleep/wake handling
───────────────────
Registers with NSWorkspace to receive power notifications:
  NSWorkspaceWillSleepNotification — snapshot session_info to resume_sessions.json
  NSWorkspaceDidWakeNotification   — unconditionally kill + restart all sessions
"""
import os
import threading
import webbrowser
import urllib.request
import logging

import rumps
from AppKit import NSWorkspace

from config.config import SERVER_URL
from config.paths import get_data_dir, get_log_dir
from ui.icon import make_status_icon

logger = logging.getLogger(__name__)


class SsmDbTunnelApp(rumps.App):
    """macOS menu-bar app that controls the SsmDbTunnel Flask server."""

    def __init__(self):
        # Pre-generate both icon states so the first swap is instant
        make_status_icon('idle',   size=22)
        make_status_icon('active', size=22)

        super().__init__(
            name='SsmDbTunnel',
            title='',                         # icon-only; count badge added dynamically
            icon=make_status_icon('idle'),
            template=False,                   # full RGBA colour, not a template mask
            quit_button=None,
        )

        self._sessions_item = rumps.MenuItem('Sessions: 0')
        self._sessions_item.set_callback(None)   # read-only display item

        self.menu = [
            rumps.MenuItem('Open Dashboard',      callback=self.open_dashboard),
            None,
            self._sessions_item,
            rumps.MenuItem('Stop All Sessions',   callback=self.stop_all),
            None,
            rumps.MenuItem('Reveal Config Files', callback=self.reveal_config),
            rumps.MenuItem('View Logs',            callback=self.view_logs),
            None,
            rumps.MenuItem('Quit',                 callback=self.quit_app),
        ]

        self._last_icon_state = 'idle'

        # Refresh session count every 5 seconds
        self._timer = rumps.Timer(self._refresh_status, 5)
        self._timer.start()

        # Register for macOS sleep/wake notifications.
        # Observer tokens are kept alive on self so they are not garbage-collected.
        self._power_observers = []
        self._register_power_notifications()

    # ------------------------------------------------------------------
    # Sleep / wake
    # ------------------------------------------------------------------

    def _register_power_notifications(self) -> None:
        try:
            nc = NSWorkspace.sharedWorkspace().notificationCenter()
            sleep_obs = nc.addObserverForName_object_queue_usingBlock_(
                'NSWorkspaceWillSleepNotification', None, None,
                lambda _n: self._on_system_sleep(),
            )
            wake_obs = nc.addObserverForName_object_queue_usingBlock_(
                'NSWorkspaceDidWakeNotification', None, None,
                lambda _n: self._on_system_wake(),
            )
            # Hold strong references so the ObjC objects are not released.
            self._power_observers = [sleep_obs, wake_obs]
            logger.info("Registered sleep/wake notifications")
        except Exception:
            logger.exception("Failed to register sleep/wake notifications; "
                             "keepalive time-jump detection will be used as fallback")

    def _on_system_sleep(self) -> None:
        """Persist the current session list right before the system suspends."""
        try:
            from config.state import session_info, session_lock
            from data.resume import save_resume_state
            with session_lock:
                snapshot = list(session_info.values())
            save_resume_state(snapshot)
            logger.info("Sleep: saved %d session(s) to resume file", len(snapshot))
        except Exception:
            logger.exception("Sleep handler error")

    def _on_system_wake(self) -> None:
        """Immediately restart all forwarding sessions after wake.

        Runs reconnection in a background thread so the Cocoa main run loop
        is never blocked (start_ssm_session sleeps 3 s per session).
        """
        logger.info("Wake notification received — launching reconnect thread")
        threading.Thread(
            target=self._reconnect_sessions_after_wake,
            daemon=True,
            name='wake-reconnect',
        ).start()

    def _reconnect_sessions_after_wake(self) -> None:
        try:
            from services.keepalive import _reconnect_dead_sessions
            _reconnect_dead_sessions()
        except Exception:
            logger.exception("Wake reconnect thread error")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_icon_state(self, icon_state: str) -> None:
        """Swap the menu-bar icon only when the state actually changes."""
        if icon_state == self._last_icon_state:
            return
        self.icon = make_status_icon(icon_state)
        self._last_icon_state = icon_state

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def open_dashboard(self, _) -> None:
        webbrowser.open(SERVER_URL)

    def _refresh_status(self, _) -> None:
        try:
            from config.state import active_sessions, session_lock
            with session_lock:
                count = len(active_sessions)
            self._sessions_item.title = f'Sessions: {count}'
            if count > 0:
                self._set_icon_state('active')
                self.title = f' {count}'
            else:
                self._set_icon_state('idle')
                self.title = ''
        except Exception:
            pass

    def stop_all(self, _) -> None:
        try:
            req = urllib.request.Request(
                f'{SERVER_URL}/api/stop',
                data=b'',
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            urllib.request.urlopen(req, timeout=5)
            rumps.notification('SsmDbTunnel', '', 'All forwarding sessions stopped.')
        except Exception as exc:
            rumps.alert(f'Failed to stop sessions:\n{exc}')

    def reveal_config(self, _) -> None:
        config_dir = get_data_dir()
        os.system(f'open "{config_dir}"')

    def view_logs(self, _) -> None:
        log_file = get_log_dir() / 'app.log'
        if log_file.exists():
            os.system(f'open "{log_file}"')
        else:
            rumps.alert('No log file found yet.')

    def quit_app(self, _) -> None:
        """Gracefully terminate all SSM sessions, clear resume state, then quit."""
        try:
            from config.state import active_sessions, session_info, session_lock
            from data.resume import clear_resume_state
            with session_lock:
                for _, proc in list(active_sessions.items()):
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                active_sessions.clear()
                session_info.clear()
            # Sessions were deliberately stopped — do not restore on next launch.
            clear_resume_state()
        except Exception:
            pass
        # Release the single-instance PID lock (written by launcher.py)
        _pid_file = get_data_dir() / '.ssmtunnel.pid'
        try:
            _pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        rumps.quit_application()
