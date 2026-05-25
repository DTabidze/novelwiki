# Backend

Flask REST API for uploads, chapter storage, AI extraction, admin review, and approved public wiki data.

## Folders

- `app/`: Flask application package.
- `app/api/`: Route blueprints grouped by feature.
- `app/models/`: Database models.
- `app/services/`: Business logic such as file parsing and extraction.
- `app/services/extraction/`: Focused helper modules used by the AI extraction pipeline.
- `instance/`: Local SQLite database and uploaded files. This is ignored by Git.

## Current Responsibilities

The current backend supports:

- Flask app factory and SQLite via SQLAlchemy.
- Admin `.txt` upload and chapter splitting.
- Per-chapter AI extraction.
- Pending review records for extracted wiki data.
- Field-level character metadata proposals for existing characters.
- Metadata normalization, dedupe, confidence, warnings, and safe auto-approval.
- Admin review endpoints for approval, rejection, edits, metadata proposal application, and character merges.
- Public `/api/wiki/*` endpoints that expose approved data only.

## API Blueprints

- `app/api/health.py`: `GET /api/health`.
- `app/api/admin_novels.py`: novel upload, chapter inspection, extraction triggers, and admin extracted-data loading.
- `app/api/admin_review.py`: review updates for extracted entities and character merges.
- `app/api/wiki.py`: approved public wiki data.

## Extraction Services

The extraction code is intentionally split so `ai_extraction_service.py` can act as an orchestrator instead of holding every rule directly.

- `app/services/chapter_parser.py`: Splits uploaded text into chapters.
- `app/services/ai_extraction_service.py`: Runs chapter extraction and persists results.
- `app/services/ai_extraction_prompts.py`: System prompts.
- `app/services/ai_extraction_schemas.py`: AI response schemas.
- `app/services/metadata_normalization.py`: Field-specific metadata normalization and similarity helpers.
- `app/services/extraction/ai_client.py`: AI client and JSON response handling.
- `app/services/extraction/memory.py`: Builds known wiki memory for extraction context.
- `app/services/extraction/identity.py`: Character identity, aliases, canonicalization, and appearance helpers.
- `app/services/extraction/progression.py`: Progression event dedupe, warnings, and current-state updates.
- `app/services/extraction/metadata.py`: Character metadata proposal creation, dedupe, warnings, and auto-approval rules.
- `app/services/extraction_service.py`: Admin extracted-data aggregation and legacy placeholder extraction support.

## Review Model

Most extracted records use `review_status` and `admin_notes`. Public APIs return approved records only.

Existing-character metadata changes are reviewed as `CharacterMetadataProposal` records. Approving a proposal updates only the proposed field on the character. This avoids making an already approved character pending again when later chapters add age, gender, origin, affiliation, titles, or species data.

Character `status` is life-status only. Position, disciple rank, faction, and titles are stored separately.

Race/species can be either confirmed from extracted evidence or assumed as the cultivation-domain default `Human` for newly approved characters with no explicit species.

## Development Schema

The app currently uses `db.create_all()` plus `ensure_development_schema()` in `app/__init__.py` to keep the local SQLite database usable while the schema is changing quickly.

This is a development convenience, not a production migration system.
