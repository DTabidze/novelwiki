# NovelWiki

A beginner-friendly MVP for generating reviewed wiki-style pages from uploaded novels.

The current version is intentionally small but end-to-end:

- Flask backend
- React frontend
- SQLite database
- REST API
- Admin upload endpoint
- AI-assisted extraction pipeline
- Admin review and merge workflow
- Public approved-data wiki view

The app should grow in layers. First store novels and chapters. Then add simple parsing. Later add AI-assisted extraction.

## Project Structure

```text
novelwiki/
  backend/          Flask API, database models, parsing/extraction services
  frontend/         React app for admin upload and reader-facing wiki pages
  docs/             Architecture, schema, API, and implementation plan
```

Start with the docs in this order:

1. `docs/architecture.md`
2. `docs/database-schema.md`
3. `docs/api-endpoints.md`
4. `docs/implementation-plan.md`

## MVP Principle

The app separates messy extraction from public wiki data:

1. Upload a `.txt` file.
2. Split it into chapters.
3. Store the novel and chapters in SQLite.
4. Run AI extraction chapter by chapter.
5. Let an admin approve, reject, edit, or merge extracted records.
6. Show only approved characters, skills, items, evidence, and progression in the public wiki.

The public wiki must not expose full chapter text. It should show reviewed facts and short evidence snippets only.
