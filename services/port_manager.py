"""
services/port_manager.py — Local port allocation and process management.
"""
import subprocess
import logging

import config.state as state
from config.config import FORWARD_BASE_PORT
from data.port_map import load_hostname_port_map, save_hostname_port_map

logger = logging.getLogger(__name__)

_LSOF = '/usr/sbin/lsof'
_KILL = '/bin/kill'


def check_port_in_use(port: int) -> tuple:
    """Return (True, [pid, ...]) if *port* is bound, else (False, [])."""
    try:
        result = subprocess.run(
            [_LSOF, '-i', f':{port}', '-t'],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            return True, result.stdout.strip().split('\n')
        return False, []
    except Exception as exc:
        logger.error("check_port_in_use(%s): %s", port, exc)
        return False, []


def kill_process_on_port(port: int) -> tuple:
    """Kill all processes bound to *port*.

    Returns (True, message) on success, (False, message) otherwise.
    """
    try:
        if not str(port).isdigit():
            return False, "Invalid port"
        result = subprocess.run(
            [_LSOF, '-i', f':{port}', '-t'],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                if pid.strip().isdigit():
                    subprocess.run([_KILL, '-9', pid.strip()])
            return True, f"Killed process(es) on port {port}"
        return False, f"No process found on port {port}"
    except Exception as exc:
        logger.error("kill_process_on_port(%s): %s", port, exc)
        return False, "Failed to kill process"


def pick_port_for_hostname(hostname: str) -> int:
    """Return the local port to use for *hostname*.

    1. If hostname has a pre-assigned port in hostname_port_map.json, use it
       (killing any occupying process first).
    2. Otherwise allocate the next free slot in the 133xx range and persist it.

    Raises RuntimeError if no free port can be found.
    """
    assigned_port = None
    with state.hostname_map_lock:
        hmap = load_hostname_port_map()
        if hostname in hmap:
            assigned_port = hmap[hostname]

    if assigned_port is not None:
        if check_port_in_use(assigned_port)[0]:
            kill_process_on_port(assigned_port)
        with state.session_lock:
            if assigned_port in state.active_sessions:
                proc = state.active_sessions[assigned_port]
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                del state.active_sessions[assigned_port]
        return assigned_port

    with state.port_id_lock:
        for offset in range(100):
            test_id = (state.port_id_counter + offset) % 100
            test_port = FORWARD_BASE_PORT + test_id
            in_use_sys, _ = check_port_in_use(test_port)
            in_use_ses = test_port in state.active_sessions
            with state.hostname_map_lock:
                in_use_other = test_port in load_hostname_port_map().values()
            if not in_use_sys and not in_use_ses and not in_use_other:
                state.port_id_counter = (test_id + 1) % 100
                with state.hostname_map_lock:
                    hmap = load_hostname_port_map()
                    hmap[hostname] = test_port
                    save_hostname_port_map(hmap)
                return test_port

    raise RuntimeError("All 133xx ports are in use")
