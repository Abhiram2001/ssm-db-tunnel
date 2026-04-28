"""
api/routes/forwarding.py — SSM forwarding session routes.

Routes:
  POST /api/setup-forwarding  — start forwarding for selected endpoints
  POST /api/stop              — stop all active sessions
  GET  /api/status            — active session count + port list
  POST /api/kill-port         — stop a single port
"""
import logging

from flask import Blueprint, request

import config.state as state
from api.middleware import safe_jsonify
from config.config import SSM_TARGET, SSM_PROFILE
from services.ssm import start_ssm_session
from services.port_manager import pick_port_for_hostname, kill_process_on_port
from data.resume import save_resume_state, clear_resume_state

logger = logging.getLogger(__name__)
bp = Blueprint('forwarding', __name__)


@bp.route('/api/setup-forwarding', methods=['POST'])
def setup_forwarding():
    """Start SSM port-forwarding sessions for the selected endpoints."""
    data = request.json or {}
    endpoints = data.get('endpoints', [])
    if not endpoints:
        return safe_jsonify({'error': 'No endpoints provided'}, 400)

    results = []
    for ep in endpoints:
        hostname = ep.get('hostname')
        remote_port = int(ep.get('port') or 3306)
        if not hostname:
            results.append({'success': False, 'error': 'Invalid endpoint'})
            continue

        try:
            local_port = pick_port_for_hostname(hostname)
        except RuntimeError as exc:
            results.append({
                'success': False,
                'error': str(exc),
                'hostname': hostname,
                'remote_port': remote_port,
            })
            continue

        try:
            process = start_ssm_session(
                SSM_TARGET, SSM_PROFILE, local_port, remote_port, hostname
            )
            with state.session_lock:
                state.active_sessions[local_port] = process
                state.session_info[local_port] = {
                    'local_port': local_port,
                    'hostname': hostname,
                    'remote_port': remote_port,
                }
            results.append({
                'success': True,
                'local_port': local_port,
                'hostname': hostname,
                'remote_port': remote_port,
            })
            logger.info("SSM session started: %s -> localhost:%s", hostname, local_port)
        except Exception:
            logger.exception("SSM session failed for %s:%s", hostname, remote_port)
            results.append({'success': False, 'error': 'Failed to start SSM session'})

    with state.session_lock:
        snapshot = list(state.session_info.values())
    if snapshot:
        save_resume_state(snapshot)

    return safe_jsonify({'success': True, 'results': results})


@bp.route('/api/stop', methods=['POST'])
def stop_forwarding():
    """Terminate all active port-forwarding sessions."""
    try:
        with state.session_lock:
            for _, proc in list(state.active_sessions.items()):
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            state.active_sessions.clear()
            state.session_info.clear()
        clear_resume_state()
        logger.info("All SSM sessions stopped")
        return safe_jsonify({'success': True, 'message': 'All sessions stopped'})
    except Exception:
        logger.exception("stop_forwarding error")
        return safe_jsonify({'error': 'Internal server error'}, 500)


@bp.route('/api/status', methods=['GET'])
def get_status():
    """Return active session count, port list, and full session details."""
    with state.session_lock:
        count = len(state.active_sessions)
        ports = list(state.active_sessions.keys())
        sessions = list(state.session_info.values())
    return safe_jsonify({'active_sessions': count, 'active_ports': ports, 'sessions': sessions})


@bp.route('/api/kill-port', methods=['POST'])
def kill_port():
    """Kill a specific local port and remove its tracked session."""
    data = request.json or {}
    port = data.get('port')
    try:
        if port is None:
            return safe_jsonify({'error': 'port required'}, 400)
        port = int(port)
        if not (1 <= port <= 65535):
            return safe_jsonify({'error': 'Port out of range'}, 400)
    except Exception:
        return safe_jsonify({'error': 'Port must be an integer'}, 400)

    try:
        success, _ = kill_process_on_port(port)
        with state.session_lock:
            if port in state.active_sessions:
                try:
                    state.active_sessions[port].terminate()
                    state.active_sessions[port].wait(timeout=5)
                except Exception:
                    try:
                        state.active_sessions[port].kill()
                    except Exception:
                        pass
                del state.active_sessions[port]
                state.session_info.pop(port, None)
        with state.session_lock:
            remaining = list(state.session_info.values())
        if remaining:
            save_resume_state(remaining)
        else:
            clear_resume_state()
        if success:
            return safe_jsonify({'success': True})
        return safe_jsonify({'error': 'Operation failed'}, 500)
    except Exception:
        logger.exception("kill_port error for port %s", port)
        return safe_jsonify({'error': 'Internal server error'}, 500)
