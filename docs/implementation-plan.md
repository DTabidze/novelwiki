# Step-by-Step Implementation Plan

## Current Status

The project has completed the first operational admin/wiki slice:

1. Admin can create/edit novel workspaces.
2. Admin can upload book/source files and parse chapters.
3. Admin can inspect books, chapters, extraction progress, and extraction run history.
4. Admin can run extraction for single chapters, ranges, full books, and continuation ranges.
5. Extracted characters, skills, items, progression events, life events, aliases, metadata proposals, and evidence are stored.
6. Admin can review chapter-grouped proposals, inspect evidence context, edit proposals, approve, reject, and merge records.
7. Public wiki endpoints expose approved data only.
8. React has an Admin workspace and routed public Wiki pages for novels, characters, progression, skills, and items.
9. Admin can edit approved canonical wiki data through the Wiki Data Editor for characters, skills, items, aliases, cultivation breakthroughs, and character relationships.
10. Admin can review canonical wiki-data history through the Wiki Edit Log with filters, details, and editor/public-page navigation.

## Phase 1: Foundation

1. Create Flask app factory.
2. Add SQLAlchemy setup.
3. Add health endpoint.
4. Add database models for novels and chapters.
5. Add database migration approach or simple `init_db` command.

## Phase 2: Upload and Chapter Storage

1. Add admin upload endpoint for source files.
2. Save the uploaded file under `backend/instance/uploads`.
3. Create `novels`, `books`, and `chapters` rows.
4. Split source text into chapters.
5. Save chapter rows.

Start with `.txt`. Add robust `.epub` and `.pdf` parsing after the text flow remains stable.

## Phase 3: Admin Chapter Review

1. Add admin novel list endpoint.
2. Add chapter list endpoint with previews.
3. Add frontend chapter verification view.

## Phase 4: AI Wiki Extraction

1. Create `ai_extraction_service`.
2. Extract important characters, skills, items, progression events, life events, aliases, and evidence.
3. Store extracted entities in the database as pending review records.
4. Keep extraction scoped to short evidence snippets, not full chapter text.

## Phase 5: Admin Review

1. Store evidence snippets for generated facts.
2. Let admins approve, reject, and edit extracted records.
3. Let admins merge duplicate character records.
4. Keep public data hidden until approved.

## Phase 5.5: Canonical Wiki Data Editor

1. Add an admin editor for approved canonical records.
2. Keep the editor separate from pending Review Queue proposal editing.
3. Support character profile edits, aliases, cultivation breakthroughs, character-skill links, and character-item links.
4. Support skill edits, skill aliases, and skill-character links.
5. Support item edits and item-character links.
6. Use searchable pickers for large character/skill/item/chapter sets.
7. Stage changes locally, show a grouped save confirmation, and persist only after Save Changes.
8. Record canonical wiki-data edits in the Wiki Edit Log.
9. Add a dedicated Edit Log page under Wiki Data with filtering, pagination, selected-change details, and responsive/mobile activity-feed rows.

Backend services supporting this phase:

- `wiki_editor_payloads.py`: editor payload validation and mutation helpers.
- `wiki_admin_responses.py`: admin/editor response serialization.
- `wiki_edit_logs.py`: edit-log diffing, creation, filtering, and pagination.
- `review_proposal_conversion.py`: review proposal type conversion helpers.

## Phase 6: Public Wiki Read API

1. Add public novel list endpoint.
2. Add public novel detail endpoint.
3. Add public character, skill, and item list endpoints.
4. Add public character, skill, and item detail endpoints.
5. Derive current character cultivation or position from approved progression events.
6. Do not expose raw chapter content in public responses.

## Current Product Priorities

1. Add user/admin accounts so Wiki Edit Log rows can record real editors instead of the placeholder `Admin`.
2. Validate Wiki Data Editor and Edit Log workflows during real editing.
3. Improve Review Queue data quality and duplicate handling.
4. Add safer admin cleanup tools for repeated extraction testing.
5. Improve book source replacement/reparse safeguards when review data exists.
6. Add robust `.epub` and `.pdf` parsing if those formats remain required.
7. Add public organization/location/timeline pages after core character/progression quality stabilizes.

## Later: Better File Support

1. Add `.epub` parsing.
2. Add `.pdf` parsing.
3. Normalize chapter parsing across file types.

## Best Practices

- Keep route files small.
- Put parsing and extraction logic in services.
- Add one feature at a time.
- Store raw chapter text so extraction can be rerun.
- Keep evidence linked to chapters.
- Do not trust AI output blindly; validate it before saving.
- Use SQLite for the MVP and switch databases only when needed.
