# NovelWiki

NovelWiki is a local-first web app for turning uploaded novels into reviewed,
wiki-style reference pages.

The current implementation is an end-to-end MVP:

- Flask backend with SQLAlchemy and SQLite
- React frontend with admin and public wiki views
- `.txt` upload and chapter splitting
- Per-chapter AI extraction
- Admin review, edit, reject, approve, and merge workflow
- Field-level character metadata proposals
- Public wiki pages that show approved data only

## Project Structure

```text
novelwiki/
  backend/          Flask API, models, chapter parsing, extraction services
  frontend/         React admin workflow and reader-facing wiki pages
  docs/             Architecture, schema, API, and planning notes
```

Start with the docs in this order:

1. `docs/architecture.md`
2. `docs/database-schema.md`
3. `docs/api-endpoints.md`
4. `docs/implementation-plan.md`

## MVP Principle

The app separates uncertain extraction from public wiki data:

1. Upload a `.txt` file.
2. Split it into chapters.
3. Store the novel and chapters in SQLite.
4. Run AI extraction chapter by chapter.
5. Store extracted records as pending review data.
6. Let an admin approve, reject, edit, or merge extracted records.
7. For existing characters, store changed metadata as field-level proposals instead of resetting the whole character to pending.
8. Show only approved characters, skills, items, relationships, life events, evidence, and progression in the public wiki.

The public wiki must not expose full chapter text. It should show reviewed facts and short evidence snippets only.

## Current Workflow

Admin workflow:

1. Upload a novel text file.
2. Verify parsed chapters.
3. Run AI extraction for selected chapters or the whole book.
4. Review a chapter-sorted queue of pending records.
5. Approve, reject, edit, or merge records.
6. Approve metadata proposals to update individual character fields.

Public wiki workflow:

1. Browse the novel library.
2. Open a novel overview.
3. Browse approved characters, cultivation progression, skills, and items.
4. Open detail pages for characters, skills, and items.

## Extraction Architecture

The AI extraction layer is split into practical modules:

- `backend/app/services/ai_extraction_service.py`: Orchestrates extraction and persistence.
- `backend/app/services/ai_extraction_prompts.py`: System prompts.
- `backend/app/services/ai_extraction_schemas.py`: Expected AI JSON schemas.
- `backend/app/services/extraction/ai_client.py`: AI client wrapper.
- `backend/app/services/extraction/memory.py`: Known wiki memory for dedupe/context.
- `backend/app/services/extraction/identity.py`: Character identity, alias, and appearance helpers.
- `backend/app/services/extraction/progression.py`: Progression event normalization and current-state helpers.
- `backend/app/services/extraction/metadata.py`: Character metadata proposal workflow.
- `backend/app/services/metadata_normalization.py`: Field-specific metadata normalization and dedupe helpers.
