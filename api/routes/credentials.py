"""
api/routes/credentials.py — DB credential management routes.

Routes:
  GET /api/credentials  — return username + database (password NEVER returned)
  PUT /api/credentials  — update credentials; omit password to keep existing
"""
import logging

from flask import Blueprint, request

from api.middleware import safe_jsonify
from data.credentials import load_credentials, save_credentials

logger = logging.getLogger(__name__)
bp = Blueprint('credentials', __name__)


@bp.route('/api/credentials', methods=['GET'])
def get_credentials():
    """Return stored credentials.  The password field is never included."""
    creds = load_credentials()
    return safe_jsonify({
        'success': True,
        'credentials': {
            'user': creds.get('user', ''),
            'database': creds.get('database', 'mysql'),
            'password_set': bool(creds.get('password')),
        },
    })


@bp.route('/api/credentials', methods=['PUT'])
def update_credentials():
    """Update stored credentials.  Omit the password field to keep the current one."""
    data = request.json or {}
    creds = load_credentials()

    if 'user' in data:
        creds['user'] = str(data['user']).strip()
    if 'database' in data:
        creds['database'] = str(data['database']).strip() or 'mysql'
    new_pw = data.get('password', '')
    if new_pw:
        creds['password'] = new_pw

    save_credentials(creds)
    logger.info("DB credentials updated (user=%s)", creds.get('user'))
    return safe_jsonify({'success': True})
