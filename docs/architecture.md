# MVP Architecture

## Goal

Build a simple web app that stores uploaded novels, splits them into chapters, and gradually produces wiki-style data.

The MVP should avoid complex AI extraction at first. Treat extraction as a replaceable service that can start with placeholders and later become smarter.

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

- `frontend/src/api/`: Functions like `getNovel(id)` and `uploadNovel(file)`.
- `frontend/src/components/`: Reusable visual pieces.
- `frontend/src/pages/`: Full pages such as `NovelOverviewPage` or `AdminUploadPage`.

## Service Boundaries

Start with these backend services:

- `file_storage_service`: Saves uploaded files.
- `chapter_parser_service`: Splits text into chapters.
- `extraction_service`: Produces placeholder wiki facts for now.

This keeps routes simple and makes future AI extraction easier to add.

## Suggested MVP Flow

1. Admin uploads a `.txt` file.
2. Backend creates a `novels` row.
3. Backend stores the original file.
4. Backend splits text into `chapters`.
5. Backend runs placeholder extraction.
6. User views generated wiki pages.

