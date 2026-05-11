from flask import Flask
from flask_cors import CORS
from sqlalchemy import text

from app.api.admin_novels import admin_novels_bp
from app.api.admin_review import admin_review_bp
from app.api.health import health_bp
from app.models import db


def ensure_development_schema(app):
    review_tables = {"characters", "skills", "items", "wiki_events"}

    with db.engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(novels)")).fetchall()
        column_names = {column[1] for column in columns}

        if "error_message" not in column_names:
            connection.execute(text("ALTER TABLE novels ADD COLUMN error_message TEXT"))

        for table_name in review_tables:
            columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            column_names = {column[1] for column in columns}

            if "review_status" not in column_names:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN review_status VARCHAR(50) NOT NULL DEFAULT 'pending'"
                    )
                )

            if "admin_notes" not in column_names:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN admin_notes TEXT"))

        connection.commit()


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
    app.register_blueprint(admin_review_bp, url_prefix="/api/admin/review")

    with app.app_context():
        db.create_all()
        ensure_development_schema(app)

    return app
