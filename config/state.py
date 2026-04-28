"""
state.py — shared mutable runtime state.

Keeping all global state in one place makes threading behaviour explicit
and prevents circular imports between service modules.

Usage:
    import config.state as state
    state.active_sessions[port] = proc  # direct attribute mutation works
"""
import threading
import subprocess
from typing import Dict

# Active SSM port-forwarding sessions: local_port → subprocess.Popen
active_sessions: Dict[int, subprocess.Popen] = {}
# Metadata for each active session: local_port → {hostname, remote_port, local_port}
session_info: Dict[int, dict] = {}
session_lock = threading.Lock()

# Port allocation counter (wraps around 0-99 over FORWARD_BASE_PORT + offset)
port_id_counter: int = 0
port_id_lock = threading.Lock()

# Serialises reads/writes to hostname_port_map.json
hostname_map_lock = threading.Lock()
