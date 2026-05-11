# NovelWiki

A beginner-friendly MVP for generating wiki-style pages from uploaded novels.

The first version is intentionally small:

- Flask backend
- React frontend
- SQLite database
- REST API
- Admin upload endpoint
- Placeholder extraction pipeline

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

Do not build the full extractor first. The earliest working milestone should:

1. Upload a `.txt` file.
2. Split it into chapters.
3. Store the novel and chapters in SQLite.
4. Show the novel overview and chapter list.
5. Add manual or placeholder extracted wiki entries.

