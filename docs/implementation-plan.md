# Step-by-Step Implementation Plan

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

## Phase 3: Read API

1. Add public novel list endpoint.
2. Add novel detail endpoint.
3. Add chapter list endpoint.
4. Add simple frontend pages that call these endpoints.

## Phase 4: Placeholder Wiki Extraction

1. Create `extraction_service`.
2. Return manually seeded or simple placeholder characters, skills, and items.
3. Store extracted entities in the database.
4. Show generated wiki pages in React.

## Phase 5: Evidence and Timeline

1. Store evidence snippets for generated facts.
2. Add character progression events.
3. Add chapter timeline endpoint.
4. Add filters for character, event type, and chapter range.

## Phase 6: Better File Support

1. Add `.epub` parsing.
2. Add `.docx` parsing.
3. Normalize chapter parsing across file types.

## Phase 7: AI Extraction Later

1. Process one chapter at a time.
2. Extract structured JSON.
3. Validate the JSON before storing it.
4. Keep evidence snippets for every generated fact.
5. Add a review screen so admins can approve generated data.

## Best Practices

- Keep route files small.
- Put parsing and extraction logic in services.
- Add one feature at a time.
- Store raw chapter text so extraction can be rerun.
- Keep evidence linked to chapters.
- Do not trust AI output blindly; validate it before saving.
- Use SQLite for the MVP and switch databases only when needed.

