"""
services/keepalive.py — MySQL keep-alive background thread.

Sends a lightweight `SELECT 1` query on every active forwarding session port
every KEEPALIVE_INTERVAL seconds.  This prevents AWS from closing idle SSM
port-forwarding tunnels due to inactivity (typical idle timeout ≈ 20 min).

Sleep/wake handling
-------------------
On macOS, time.time() (wall clock) advances while the machine is asleep but
time.monotonic() does not.  The keepalive loop tracks wall-clock elapsed time;
if a cycle takes more than 2× KEEPALIVE_INTERVAL the machine was likely
suspended.

Reconnect strategy
------------------
After a sleep, AWS will have terminated the SSM tunnels from its end regardless
of whether the subprocess has exited yet.  _reconnect_dead_sessions() therefore
unconditionally kills every tracked process and restarts them all.

Session source priority on wake:
  1. state.session_info  (populated while the app is running)
  2. resume_sessions.json  (survives scenarios where in-memory state was cleared
     before wake fires)
"""
import time
import threading
import logging

import pymysql
import pymysql.cursors

import config.state as state
from config.config import KEEPALIVE_INTERVAL
from data.credentials import load_credentials
from data.resume import load_resume_state, save_resume_state, clear_resume_state

logger = logging.getLogger(__name__)

_SLEEP_DETECT_MULTIPLIER = 2

_reconnect_lock = threading.Lock()
_last_reconnect_wall: float = 0.0


def _reconnect_dead_sessions() -> None:
    """Unconditionally restart all tracked SSM sessions.

    Called immediately on system wake (via NSWorkspace notification in
    ui/menubar.py) and also by the keepalive loop when a large wall-clock gap
    is detected.
    """
    if not _reconnect_lock.acquire(blocking=False):
        logger.debug("Wake reconnect already in progress — skipping duplicate call")
        return

    global _last_reconnect_wall
    _last_reconnect_wall = time.time()

    try:
        from config.config import SSM_TARGET, SSM_PROFILE
        from services.ssm import start_ssm_session

        with state.session_lock:
            to_restart = list(state.session_info.values())

        if not to_restart:
            to_restart = load_resume_state()

        if not to_restart:
            logger.info("Wake reconnect: no sessions to restore")
            return

        logger.info("Wake reconnect: will restart %d session(s)", len(to_restart))

        with state.session_lock:
            for proc in state.active_sessions.values():
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            state.active_sessions.clear()
            state.session_info.clear()

        restarted = []
        for info in to_restart:
            local_port  = info['local_port']
            hostname    = info['hostname']
            remote_port = info['remote_port']
            try:
                process = start_ssm_session(
                    SSM_TARGET, SSM_PROFILE, local_port, remote_port, hostname
                )
                with state.session_lock:
                    state.active_sessions[local_port] = process
                    state.session_info[local_port] = info
                restarted.append(info)
                logger.info("Wake reconnect OK: %s -> localhost:%s", hostname, local_port)
            except Exception:
                logger.exception(
                    "Wake reconnect failed: %s -> localhost:%s", hostname, local_port
                )

        if restarted:
            save_resume_state(restarted)
        else:
            clear_resume_state()

    finally:
        _reconnect_lock.release()


def _keepalive_loop() -> None:
    last_wall = time.time()
    while True:
        time.sleep(KEEPALIVE_INTERVAL)

        now = time.time()
        elapsed = now - last_wall
        last_wall = now

        if elapsed > KEEPALIVE_INTERVAL * _SLEEP_DETECT_MULTIPLIER:
            since_last = now - _last_reconnect_wall
            if since_last < KEEPALIVE_INTERVAL * 3:
                logger.info(
                    "Time-jump detected (%.0fs) but reconnect ran %.0fs ago — skipping duplicate",
                    elapsed, since_last,
                )
                continue
            logger.info(
                "System wake detected (%.0fs gap) — reconnecting dead sessions", elapsed,
            )
            _reconnect_dead_sessions()
            continue

        with state.session_lock:
            ports = list(state.active_sessions.keys())

        if not ports:
            continue

        creds = load_credentials()
        if not creds.get('user'):
            logger.debug("Keep-alive skipped: no credentials configured")
            continue

        for port in ports:
            try:
                conn = pymysql.connect(
                    host='127.0.0.1',
                    port=port,
                    user=creds['user'],
                    password=creds.get('password', ''),
                    database=creds.get('database') or 'mysql',
                    connect_timeout=10,
                    read_timeout=10,
                    write_timeout=10,
                    cursorclass=pymysql.cursors.Cursor,
                )
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                conn.close()
                logger.debug("Keep-alive OK on localhost:%s", port)
            except Exception as exc:
                logger.warning("Keep-alive failed on localhost:%s — %s", port, exc)
                with state.session_lock:
                    proc = state.active_sessions.get(port)
                    if proc is not None and proc.poll() is not None:
                        exit_code = proc.poll()
                        del state.active_sessions[port]
                        state.session_info.pop(port, None)
                        logger.info(
                            "Removed dead SSM session on port %s (exit code %s)",
                            port, exit_code,
                        )
                with state.session_lock:
                    remaining = list(state.session_info.values())
                if remaining:
                    save_resume_state(remaining)
                else:
                    clear_resume_state()


def start_keepalive() -> threading.Thread:
    """Start the keep-alive daemon thread and return it."""
    thread = threading.Thread(target=_keepalive_loop, daemon=True, name='keepalive')
    thread.start()
    return thread
