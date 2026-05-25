# Architecture

## Goal

Build a simple web app that stores uploaded novels, splits them into chapters, extracts wiki-style facts, and keeps all extracted data behind admin review.

Public pages show approved wiki data only. Raw chapter text and unreviewed AI output stay in the admin side.

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

The backend owns storage, extraction, review state, and public API filtering. The frontend owns the admin workflow and public wiki presentation.

## Backend Folders

- `backend/app/`: Main Flask app package.
- `backend/app/api/`: HTTP route blueprints. Keep request/response handling here.
- `backend/app/models/`: SQLAlchemy database models.
- `backend/app/services/`: App logic that should not live directly in route files.
- `backend/app/services/extraction/`: Focused extraction helpers used by the AI extraction orchestrator.
- `backend/instance/`: Local runtime files such as SQLite databases and uploaded files.

Current API blueprints:

- `health.py`: Health check endpoint.
- `admin_novels.py`: Upload, chapter listing, extraction triggers, and admin data loading.
- `admin_review.py`: Review updates, metadata proposal approval, and character merge.
- `wiki.py`: Approved public wiki data.

## Frontend Folders

- `frontend/src/main.jsx`: React entrypoint and router mount.
- `frontend/src/App.jsx`: Top-level app state, route definitions, and admin/wiki view switching.
- `frontend/src/api.js`: Shared frontend API helper.
- `frontend/src/components/admin/`: Admin review components.
- `frontend/src/components/wiki/`: Public wiki components.
- `frontend/src/utils/`: Small frontend utility functions.
- `frontend/src/styles.css`: Current shared MVP styling.

The frontend currently keeps CSS in one shared stylesheet. The public wiki and temporary admin review UI share the same Vite/React app.

## Public Wiki Navigation

The public wiki starts at the novel library. Users choose a novel first, then browse that novel's approved wiki data.

Current public routes:

- `/wiki/novels`: Novel library.
- `/wiki/novels/:novelId`: Selected novel overview.
- `/wiki/novels/:novelId/characters`: Character list for the selected novel.
- `/wiki/novels/:novelId/characters/:characterId`: Character detail page.
- `/wiki/novels/:novelId/characters/:characterId/progression`: Full character progression page.
- `/wiki/novels/:novelId/cultivation`: Novel-level cultivation/progression page.
- `/wiki/novels/:novelId/skills`: Skill list.
- `/wiki/novels/:novelId/skills/:skillId`: Skill detail page.
- `/wiki/novels/:novelId/items`: Item list.
- `/wiki/novels/:novelId/items/:itemId`: Item detail page.

Novel-specific sidebar navigation should appear only after a novel is selected. The selected novel becomes the context for character, cultivation, skill, and item pages.

## Service Boundaries

Current backend service boundaries:

- `chapter_parser.py`: Splits uploaded `.txt` content into chapter records.
- `ai_extraction_service.py`: Main extraction orchestrator. It calls the AI, saves records, attaches evidence, and coordinates helper modules.
- `ai_extraction_prompts.py`: AI system prompts for extraction and progression audit passes.
- `ai_extraction_schemas.py`: JSON schema definitions for AI responses.
- `metadata_normalization.py`: Field-specific normalization for metadata values.
- `extraction/ai_client.py`: AI client setup and response parsing.
- `extraction/memory.py`: Existing approved/pending wiki memory passed into extraction.
- `extraction/identity.py`: Character identity, alias, canonical-name, appearance, and merge-support helpers.
- `extraction/progression.py`: Progression event helpers, dedupe, review warnings, and current character state updates.
- `extraction/metadata.py`: Character metadata extraction, proposal creation, dedupe, warnings, and safe auto-approval rules.
- `extraction_service.py`: Admin data aggregation and legacy placeholder extraction support.

Routes should stay thin. Extraction rules and persistence behavior should live in services.

## Admin Extraction And Review Flow

1. Admin uploads a `.txt` file.
2. Backend creates a `novels` row.
3. Backend stores the original file.
4. Backend splits text into `chapters`.
5. Admin runs AI extraction for selected chapters or the whole book.
6. Backend builds known wiki memory and sends chapter text to the extraction pipeline.
7. Backend stores pending characters, skills, items, character-skill links, character-item links, progression events, life events, aliases, metadata proposals, and evidence.
8. Admin reviews records in a single chapter-sorted queue.
9. Admin can hide approved or rejected cards while reviewing.
10. Admin approves, rejects, edits, or merges records.
11. Public wiki routes read approved records through `/api/wiki/*`.

## Character Metadata Workflow

Character metadata is split into approved character fields and pending field-level proposals.

Approved character fields include age text, gender, race/species, origin, affiliation, life status, titles, and current progression summary fields.

For new characters, metadata can be stored on the pending character record and reviewed with that character. For existing characters, new metadata does not make the whole character pending again. Instead, the backend creates `CharacterMetadataProposal` rows for changed or missing fields.

Metadata proposals preserve:

- old value
- raw proposed value
- display proposed value
- normalized value
- confidence score
- extraction reason
- evidence
- review warnings

Approving a metadata proposal updates only that one character field. Rejecting it leaves the character unchanged.

Status is life-status only: `alive`, `dead`, `historical`, `missing`, `sealed`, `reincarnated`, or `unknown`. Sect roles and disciple ranks belong in `current_position`, `titles`, or `faction_or_affiliation`.

Race/species defaults to `Human` only as an implicit cultivation-domain assumption when a newly approved character has no explicit species. The backend records this as `race_or_species_source = implicit_default` and `race_or_species_confidence = assumed`. Explicit species evidence is stored as extracted/confirmed and can override the implicit default through review.

## Public Data Boundary

Public routes must:

- Return approved records only.
- Include short evidence snippets and chapter references.
- Avoid exposing full chapter text.
- Show current character cultivation and position summaries without exposing the full progression timeline on the character detail page.
- Link to full detail pages for cultivation progression, skills, and items when needed.

## Public Wiki Pages

The current public wiki includes:

- Novel library and novel overview.
- Character browser.
- Character detail pages with header/profile area, quick facts, about text, aliases, current cultivation, skills, items, subtle life events, and evidence highlights.
- Character progression detail pages.
- Novel cultivation/progression overview.
- Skill browser and skill detail pages with approved character relationships.
- Item browser and item detail pages with approved character relationships.

Recent events are intentionally not prominent on character pages because they can be spoilers.
