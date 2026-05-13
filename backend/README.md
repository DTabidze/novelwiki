# Backend

Flask REST API for uploads, chapter storage, AI extraction, admin review, and approved public wiki data.

## Folders

- `app/`: Flask application package.
- `app/api/`: Route blueprints grouped by feature.
- `app/models/`: Database models.
- `app/services/`: Business logic such as file parsing and extraction.
- `instance/`: Local SQLite database and uploaded files. This is ignored by Git.

## First Goal

The current backend supports:

- Flask app factory and SQLite via SQLAlchemy.
- Admin `.txt` upload and chapter splitting.
- Per-chapter AI extraction.
- Admin review endpoints for approval, rejection, edits, and character merges.
- Public `/api/wiki/*` endpoints that expose approved data only.
