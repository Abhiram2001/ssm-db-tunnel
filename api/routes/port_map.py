"""
api/routes/port_map.py — Hostname → local-port map management routes.

Routes:
  GET /api/port-map  — return the full map
  PUT /api/port-map  — replace the map, stopping/restarting affected sessions
"""
import re
import logging
from typing import Dict

from flask import Blueprint, request

import config.state as state
from api.middleware import safe_jsonify
from config.config import SSM_TARGET, SSM_PROFILE
from services.ssm import start_ssm_session
from services.port_manager import check_port_in_use, kill_process_on_port
from data.port_map import load_hostname_port_map, save_hostname_port_map

logger = logging.getLogger(__name__)
bp = Blueprint('port_map', __name__)


@bp.route('/api/port-map', methods=['GET'])
def get_port_map():
    """Return the full hostname → local_port mapping."""
    with state.hostname_map_lock:
        hmap = load_hostname_port_map()
    return safe_jsonify({'success': True, 'port_map': hmap})


@bp.route('/api/port-map', methods=['PUT'])
def update_port_map():
    """Replace the port map and stop/restart affected sessions.

    Body:   { "port_map": { "<hostname>": <local_port>, ... } }
    Response: { "success": true, "sessions_stopped": [...], "sessions_restarted": [...] }
    """
    data = request.json or {}
    new_map_raw = data.get('port_map')
    if not isinstance(new_map_raw, dict):
        return safe_jsonify({'error': 'port_map must be a JSON object'}, 400)

    new_map: Dict[str, int] = {}
    for h, p in new_map_raw.items():
        h_str = str(h).strip()
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]$', h_str):
            return safe_jsonify({'error': f'Invalid hostname: {h_str}'}, 400)
        try:
            p_int = int(p)
        except (TypeError, ValueError):
            return safe_jsonify({'error': f'Invalid port for {h_str}'}, 400)
        if not (1 <= p_int <= 65535):
            return safe_jsonify({'error': f'Port out of range for {h_str}'}, 400)
        new_map[h_str] = p_int

    with state.hostname_map_lock:
        old_map = load_hostname_port_map()

    sessions_stopped: list = []
    sessions_restarted: list = []

    for hostname, old_port in old_map.items():
        if hostname not in new_map or new_map[hostname] != old_port:
            with state.session_lock:
                if old_port in state.active_sessions:
                    try:
                        state.active_sessions[old_port].terminate()
                        state.active_sessions[old_port].wait(timeout=3)
                    except Exception:
                        try:
                            state.active_sessions[old_port].kill()
                        except Exception:
                            pass
                    del state.active_sessions[old_port]
                state.session_info.pop(old_port, None)
            kill_process_on_port(old_port)
            sessions_stopped.append({'hostname': hostname, 'local_port': old_port})
            logger.info("Stopped session for %s (port %s) due to config change", hostname, old_port)

    for hostname, new_port in new_map.items():
        if hostname in old_map and old_map[hostname] != new_port:
            try:
                if check_port_in_use(new_port)[0]:
                    kill_process_on_port(new_port)
                process = start_ssm_session(SSM_TARGET, SSM_PROFILE, new_port, 3306, hostname)
                with state.session_lock:
                    state.active_sessions[new_port] = process
                    state.session_info[new_port] = {
                        'local_port': new_port,
                        'hostname': hostname,
                        'remote_port': 3306,
                    }
                sessions_restarted.append({'hostname': hostname, 'local_port': new_port})
                logger.info("Restarted session for %s on new port %s", hostname, new_port)
            except Exception:
                logger.exception("Failed to restart session for %s on port %s", hostname, new_port)

    with state.hostname_map_lock:
        save_hostname_port_map(new_map)

    return safe_jsonify({
        'success': True,
        'sessions_stopped': sessions_stopped,
        'sessions_restarted': sessions_restarted,
    })
