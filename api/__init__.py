"""
api/__init__.py — Flask application factory.

create_app() wires together all blueprints, middleware, and the index route.
"""
import os

from flask import Flask, render_template

from config.paths import get_bundle_dir
from api.middleware import set_security_headers
from api.routes import forwarding, endpoints, port_map, credentials


def create_app() -> Flask:
    """Create and configure the Flask application."""
    flask_app = Flask(
        __name__,
        template_folder=str(get_bundle_dir() / 'templates'),
    )
    flask_app.secret_key = os.urandom(24)
    flask_app.jinja_env.autoescape = True

    flask_app.after_request(set_security_headers)

    flask_app.register_blueprint(forwarding.bp)
    flask_app.register_blueprint(endpoints.bp)
    flask_app.register_blueprint(port_map.bp)
    flask_app.register_blueprint(credentials.bp)

    @flask_app.route('/')
    def index():
        return render_template('index.html')

    return flask_app
