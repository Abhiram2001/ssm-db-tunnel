"""
api/routes/endpoints.py — Endpoint listing routes.

Routes:
  GET /api/endpoints         — list all endpoints from hostname_port_map.json
  GET /api/scrape-endpoints  — backward-compat alias
"""
import logging

from flask import Blueprint

import config.state as state
from api.middleware import safe_jsonify
from data.port_map import load_hostname_port_map

logger = logging.getLogger(__name__)
bp = Blueprint('endpoints', __name__)


@bp.route('/api/endpoints', methods=['GET'])
@bp.route('/api/scrape-endpoints', methods=['GET'])
def list_endpoints():
    """Return all database endpoints from hostname_port_map.json."""
    try:
        with state.hostname_map_lock:
            hmap = load_hostname_port_map()
        endpoints = [
            {'hostname': h, 'port': 3306, 'local_port': lp}
            for h, lp in hmap.items()
        ]
        return safe_jsonify({'success': True, 'endpoints': endpoints})
    except Exception:
        logger.exception("list_endpoints error")
        return safe_jsonify({'success': False, 'error': 'Failed to load endpoints'}, 500)
