"""
api/middleware.py — Flask response middleware and output sanitization.
"""
import bleach
from flask import jsonify


def _sanitize_text(text: str) -> str:
    if text is None:
        return ''
    return bleach.clean(str(text), tags=[], attributes={}, protocols=[], strip=True)


def _sanitize_payload(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(v) for v in obj]
    if isinstance(obj, str):
        return _sanitize_text(obj)
    return obj


def safe_jsonify(payload, status_code: int = 200):
    """Sanitize *payload* and return a Flask JSON response tuple."""
    return jsonify(_sanitize_payload(payload)), status_code


def set_security_headers(response):
    """Attach security headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    )
    return response
