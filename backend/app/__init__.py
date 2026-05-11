from flask import Flask
from flask_cors import CORS

from app.api.admin_novels import admin_novels_bp
from app.api.health import health_bp
from app.models import db


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///novelwiki.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER="uploads",
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )

    CORS(app)
    db.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(admin_novels_bp, url_prefix="/api/admin")

    with app.app_context():
        db.create_all()

    return app
