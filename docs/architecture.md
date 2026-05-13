# MVP Architecture

## Goal

Build a simple web app that stores uploaded novels, splits them into chapters, and gradually produces wiki-style data.

The MVP keeps AI extraction behind an admin review layer. Public pages should show only approved wiki data, not raw or unreviewed AI output.

## High-Level Shape

```text
React frontend
    |
    | REST API over HTTP
    v
Flask backend
    |
    | SQLAlchemy models
    v
SQLite database
```

## Backend Folders

- `backend/app/`: Main Flask app package.
- `backend/app/api/`: HTTP route files. Keep request/response handling here.
- `backend/app/models/`: SQLAlchemy database models.
- `backend/app/services/`: App logic that should not live directly in route files.
- `backend/instance/`: Local runtime files such as SQLite databases and uploaded files.

## Frontend Folders

- `frontend/src/main.jsx`: Current MVP React app, including Admin and Wiki views.
- `frontend/src/styles.css`: Current MVP styling.

The frontend can be split into `api/`, `components/`, and `pages/` later when the UI grows.

## Service Boundaries

Start with these backend services:

- `file_storage_service`: Saves uploaded files.
- `chapter_parser_service`: Splits text into chapters.
- `ai_extraction_service`: Extracts structured wiki facts from one chapter at a time.
- `extraction_service`: Collects extracted records for admin review and still supports placeholder clearing/testing.

This keeps routes simple and makes future AI extraction easier to add.

## Suggested MVP Flow

1. Admin uploads a `.txt` file.
2. Backend creates a `novels` row.
3. Backend stores the original file.
4. Backend splits text into `chapters`.
5. Admin runs AI extraction on selected chapters.
6. Backend stores pending characters, skills, items, progression, life events, aliases, and evidence.
7. Admin reviews, edits, rejects, approves, or merges extracted records.
8. Public Wiki view reads approved records through `/api/wiki/*`.

## Public Data Boundary

Public routes must:

- Return approved records only.
- Include short evidence snippets and chapter references.
- Avoid exposing full chapter text.
- Derive current character cultivation or position from approved progression events where possible.
