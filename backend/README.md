# Backend

Flask REST API for uploads, chapter storage, and generated wiki data.

## Folders

- `app/`: Flask application package.
- `app/api/`: Route blueprints grouped by feature.
- `app/models/`: Database models.
- `app/services/`: Business logic such as file parsing and extraction.
- `instance/`: Local SQLite database and uploaded files. This is ignored by Git.

## First Goal

Create a Flask app factory, connect SQLite, and add simple health and novel endpoints.

