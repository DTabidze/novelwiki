# Step-by-Step Implementation Plan

## Current Status

The project has completed the first real vertical slice:

1. Admin can upload `.txt` novels.
2. Backend splits novels into chapters.
3. Admin can run AI extraction per chapter.
4. Extracted characters, skills, items, progression events, life events, aliases, and evidence are stored.
5. Admin can approve, reject, edit, and merge reviewed records.
6. Public wiki endpoints expose approved data only.
7. React has an Admin view and a public Wiki view with clickable characters, skills, and items.

## Phase 1: Foundation

1. Create Flask app factory.
2. Add SQLAlchemy setup.
3. Add health endpoint.
4. Add database models for novels and chapters.
5. Add database migration approach or simple `init_db` command.

## Phase 2: Upload and Chapter Storage

1. Add admin upload endpoint for `.txt` files only.
2. Save the uploaded file under `backend/instance/uploads`.
3. Create a `novels` row.
4. Split the text into chapters.
5. Save chapter rows.

Start with `.txt`. Add `.epub` and `.docx` after the first flow works.

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

## Phase 6: Public Wiki Read API

1. Add public novel list endpoint.
2. Add public novel detail endpoint.
3. Add public character, skill, and item list endpoints.
4. Add public character, skill, and item detail endpoints.
5. Derive current character cultivation or position from approved progression events.
6. Do not expose raw chapter content in public responses.

## Next Phase: Character Relationships

1. Add explicit character-skill relationships.
2. Add explicit character-item relationships.
3. Review relationships before showing them publicly.
4. Display approved skills and items on character pages.

## Later: Better File Support

1. Add `.epub` parsing.
2. Add `.docx` parsing.
3. Normalize chapter parsing across file types.

## Best Practices

- Keep route files small.
- Put parsing and extraction logic in services.
- Add one feature at a time.
- Store raw chapter text so extraction can be rerun.
- Keep evidence linked to chapters.
- Do not trust AI output blindly; validate it before saving.
- Use SQLite for the MVP and switch databases only when needed.
