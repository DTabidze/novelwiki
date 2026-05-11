from flask import Flask
from flask_cors import CORS

from app.api.health import health_bp


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///novelwiki.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    CORS(app)

    app.register_blueprint(health_bp, url_prefix="/api")

    return app

