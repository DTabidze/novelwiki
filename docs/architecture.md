# Architecture

## Goal

Build a local-first editorial operations app that stores novel workspaces, manages book source files, splits them into chapters, extracts wiki-style facts, and keeps all extracted data behind admin review.

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

The backend owns storage, extraction, review state, run history, and public API filtering. The frontend owns the admin workspace workflow and public wiki presentation.

## Backend Folders

- `backend/app/`: Main Flask app package.
- `backend/app/api/`: HTTP route blueprints. Keep request/response handling here.
- `backend/app/models/`: SQLAlchemy database models.
- `backend/app/services/`: App logic that should not live directly in route files.
- `backend/app/services/extraction/`: Focused extraction helpers used by the AI extraction orchestrator.
- `backend/instance/`: Local runtime files such as SQLite databases and uploaded files.

Current API blueprints:

- `health.py`: Health check endpoint.
- `admin_novels.py`: Novel/book management, chapter listing, extraction run creation/cancel/resume, and admin data loading.
- `admin_review.py`: Review updates, evidence context, metadata proposal approval, character merge, canonical Wiki Data Editor routes, and Wiki Edit Log routes. Route handlers should delegate domain behavior to services.
- `wiki.py`: Approved public wiki data.

## Frontend Folders

- `frontend/src/main.jsx`: React entrypoint and router mount.
- `frontend/src/App.jsx`: Top-level public wiki routes and admin app mounting.
- `frontend/src/api.js`: Shared frontend API helper.
- `frontend/src/admin/`: Admin shell, novel library, workspace pages, extraction UI, review UI, and admin CSS modules.
- `frontend/src/components/wiki/`: Public wiki components.
- `frontend/src/utils/`: Small frontend utility functions.
- `frontend/src/admin/styles/`: Admin CSS split by domain.

The public wiki and admin workspace share the same Vite/React app. Admin styling is separated into domain CSS modules imported through `frontend/src/admin/admin.css`.

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
- `skill_categories.py` / `item_categories.py`: Supported canonical category values for editor/API validation.
- `wiki_editor_payloads.py`: Canonical Wiki Data Editor payload validation and relationship/alias update helpers.
- `wiki_edit_logs.py`: Wiki Edit Log value normalization, snapshot diffing, edit-log row creation, parent-label enrichment, filtering, and pagination.
- `wiki_admin_responses.py`: Admin/review/editor response serialization for canonical records, evidence, chapter references, aliases, and approved relationships.
- `review_proposal_conversion.py`: Review proposal type conversion helpers for skill/item proposals, including evidence and relationship movement.
- `metadata_normalization.py`: Field-specific normalization for metadata values.
- `extraction/ai_client.py`: AI client setup and response parsing.
- `extraction/memory.py`: Existing approved/pending wiki memory passed into extraction.
- `extraction/identity.py`: Character identity, alias, canonical-name, appearance, and merge-support helpers.
- `extraction/progression.py`: Progression event helpers, dedupe, review warnings, and current character state updates.
- `extraction/metadata.py`: Character metadata extraction, proposal creation, dedupe, warnings, and safe auto-approval rules.
- `extraction_service.py`: Admin data aggregation and legacy placeholder extraction support.

Routes should stay thin. Extraction rules and persistence behavior should live in services.

## Admin Workspace Flow

1. Admin creates a novel workspace with title, author, description, and optional cover.
2. Admin uploads book source files into that workspace.
3. Backend stores each book, saves the uploaded source file, and parses chapters.
4. Admin runs extraction for a single chapter, chapter range, full book, or continuation scope.
5. Backend creates an `ExtractionRun` and per-chapter `ExtractionRunChapter` rows before processing starts.
6. Backend builds known wiki memory and sends chapter text through the main extraction prompt, progression audit prompt, and deterministic progression fallback.
7. Backend stores pending characters, skills, items, character-skill links, character-item links, progression events, life events, aliases, metadata proposals, and evidence.
8. Admin reviews records in a chapter-collapsible Review Queue.
9. Admin opens evidence context, edits proposals before approval, approves, rejects, or merges records.
10. Admin corrects already-approved canonical data in the Wiki Data Editor when needed.
11. Public wiki routes read approved records through `/api/wiki/*`.

## Wiki Data Editor Architecture

The Wiki Data Editor is the canonical-data editing surface for approved wiki records. It is intentionally separate from the Review Queue:

- Review Queue edits AI-generated pending proposals before approval.
- Wiki Data Editor edits approved records already used by public wiki pages.

Backend routes live in `admin_review.py` under `/api/admin/review/wiki-data/*`. Route handlers should stay thin and delegate behavior to services:

- `wiki_editor_payloads.py` validates and applies canonical editor payloads.
- `wiki_admin_responses.py` builds the editor/review response shapes.
- `wiki_edit_logs.py` records and queries canonical wiki-data changes.

Frontend code lives under `frontend/src/admin/editor/`:

- `WikiDataEditorPage.jsx`: coordinator for URL state, fetching, record selection, save/discard flow, and modal orchestration.
- `components/CharacterEditor.jsx`: character canonical editor panel.
- `components/SkillEditor.jsx`: skill canonical editor panel.
- `components/ItemEditor.jsx`: item canonical editor panel.
- `components/RelationshipEditors.jsx`: inline editors for aliases, cultivation breakthroughs, and character/skill/item relationships.
- `components/ReferencePickers.jsx`: searchable pickers for skills, characters, and items.
- `components/ChapterReferencePicker.jsx`: scalable chapter number/search picker.
- `components/EditorModals.jsx`: save-confirmation, delete-confirmation, and unsaved-change review modals.
- `editorDrafts.js`: API-to-draft conversion helpers and category lists.
- `editorChangeSummary.js`: pending-change summary generation for confirmation modals.
- `editorConfig.js`: entity tabs, section config, URL initialization, and field labels.

The editor keeps changes in local draft state until the admin confirms Save Changes. Confirmation modals group changes as updated, added, or removed. Navigation away from a dirty record is guarded and shows the pending changes before save/discard.

Large canonical lists use a drawer/browser pattern. The entity list is secondary to the active editor panel, especially on laptop-width screens.

Chapter references must save chapter IDs, not chapter numbers. The chapter picker resolves by chapter ID, chapter number, or search query through the backend chapter-search endpoint.

## Wiki Edit Log Architecture

The Wiki Edit Log is an admin audit surface for canonical wiki-data changes. It is separate from the editor so admins can review historical changes without opening an editable record.

Backend route:

- `GET /api/admin/review/wiki-data/novels/:novel_id/edit-log`

The endpoint supports search, entity type, change type, date range, admin, page, and page-size filters. It returns grouped-ready log rows plus pagination metadata.

Edit-log rows are written when canonical editor PATCH/direct alias endpoints commit approved-data changes. Logs capture:

- operation: added, updated, or removed
- edited context entity, such as character, skill, or item
- changed record/value, such as alias text or linked character
- field/type label
- old and new values where applicable
- parent entity IDs for contextual display and editor navigation
- edited-by text, currently `Admin` until real user accounts exist

Frontend route:

- `/admin/novels/:novelId/edit-log`

The desktop layout keeps filters and details visible while the log list scrolls. Medium and mobile layouts stack details below the list, and mobile rows render as compact activity-feed cards.

## Extraction Run Behavior

Extraction runs are historical records. Continuing a failed or canceled extraction creates a new run instead of mutating the original run back to running.

Run cards should communicate:

- requested chapter range
- completed range
- current chapter while running
- failed or canceled chapter when applicable
- records created
- warnings
- duration or error message

Canceling a run stops future work and keeps already-created review data. It is not a destructive cleanup action. If an AI request is already in flight, the backend checks the run status before saving output and discards canceled output to avoid ghost review items.

Raw AI response logging is opt-in through `AI_LOG_RAW_RESPONSES=true` and should be used only for local debugging.

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

## Progression Workflow

Progression extraction combines three layers:

- main chapter extraction
- second-pass progression audit extraction
- deterministic direct cultivation detection for obvious level statements

Progression rows are deduped by character, progression type, and normalized value. Rejected progression rows do not block later proposals for the same value, because a reviewer may reject a weak attribution and later receive stronger evidence from another chapter.

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
