# REST API Endpoints

Use `/api` as the API prefix. Responses follow the project wrapper:

```json
{
  "data": {},
  "error": null
}
```

Errors return the same shape with `data: null` and an error message.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check that the backend is running |

## Admin Novels And Books

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/novels` | List admin novel workspaces with review/extraction counts |
| POST | `/api/admin/novels` | Create a novel workspace without uploading a book |
| PATCH | `/api/admin/novels/:novel_id` | Edit novel title, author, description, cover, or status |
| POST | `/api/admin/novels/upload` | Legacy one-step `.txt` novel upload |
| GET | `/api/admin/novels/:novel_id/books` | List books/source files for a novel |
| POST | `/api/admin/novels/:novel_id/books/upload` | Upload and parse a source file into a book |
| PATCH | `/api/admin/novels/:novel_id/books/:book_id` | Edit book number/title metadata |
| POST | `/api/admin/novels/:novel_id/books/:book_id/source` | Replace a book source file without automatically reparsing |
| POST | `/api/admin/novels/:novel_id/books/:book_id/reparse` | Destructively delete parsed chapters for that book and reparse its current source |

Supported book upload file types are currently UI-focused around `.txt`, `.pdf`, and `.epub`; parsing support should be verified before relying on non-text files in production workflows.

## Admin Chapters

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/novels/:novel_id/chapters` | List parsed chapters with book context, previews, review counts, and warning counts |
| POST | `/api/admin/novels/:novel_id/process` | Legacy placeholder processing endpoint |

## Admin Extraction Runs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/novels/:novel_id/extraction-runs` | List extraction run history |
| GET | `/api/admin/novels/:novel_id/extraction-runs/:run_id` | Load one extraction run with per-chapter status |
| POST | `/api/admin/novels/:novel_id/extraction-runs` | Start a new extraction run |
| POST | `/api/admin/novels/:novel_id/extraction-runs/:run_id/cancel` | Cancel a running/queued extraction run |
| POST | `/api/admin/novels/:novel_id/chapters/:chapter_id/extract` | Legacy single-chapter extraction endpoint |

Extraction run creation supports scopes such as single chapter, chapter range, full book, and continuation ranges. Continue/resume creates a new historical run rather than mutating the original failed/canceled run.

Canceling a run keeps already-created review data and prevents future or canceled in-flight output from being saved.

## Admin Extracted Data

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/novels/:novel_id/extracted-data` | Load all extracted admin review records with source chapter references |

The admin UI groups this data into the Review Queue. Records may be pending, approved, or rejected depending on filters.

## Admin Review

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/review/chapters/:chapter_id/context?evidence=&radius=1` | Load nearby source paragraphs around an evidence snippet |
| PATCH | `/api/admin/review/:entity_type/:id` | Edit, approve, reject, or add admin notes to a review record |
| POST | `/api/admin/review/characters/:source_id/merge` | Merge one character into another |

Supported review entity types:

- `characters`
- `character_metadata_proposals`
- `progression_events`
- `skills`
- `items`
- `character_skills`
- `character_items`
- `life_events`
- `events`

Approving a `character_metadata_proposals` record applies only that proposed field to the character. Editing a review item changes the proposal being reviewed and does not automatically approve it.

## Admin Wiki Data Editor

These endpoints edit canonical approved wiki data, not pending Review Queue proposals.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/review/wiki-data/novels/:novel_id/characters` | List approved characters with aliases, cultivation, skills, items, evidence, and metadata history for the editor |
| GET | `/api/admin/review/wiki-data/novels/:novel_id/skills?q=` | List approved skills with aliases, character links, and evidence |
| GET | `/api/admin/review/wiki-data/novels/:novel_id/items?q=` | List approved items with character links and evidence |
| GET | `/api/admin/review/wiki-data/novels/:novel_id/chapters/search?chapter_id=&number=&q=&limit=` | Resolve/search chapters for chapter reference pickers |
| GET | `/api/admin/review/wiki-data/novels/:novel_id/edit-log` | List canonical wiki-data edit log rows with filters and pagination |
| PATCH | `/api/admin/review/wiki-data/characters/:character_id` | Update an approved character and its aliases, cultivation events, skill links, and item links |
| PATCH | `/api/admin/review/wiki-data/skills/:skill_id` | Update an approved skill and its aliases/character links |
| PATCH | `/api/admin/review/wiki-data/items/:item_id` | Update an approved item and its character links |
| POST | `/api/admin/review/wiki-data/characters/:character_id/aliases` | Legacy/direct create character alias |
| PATCH | `/api/admin/review/wiki-data/character-aliases/:alias_id` | Legacy/direct update character alias |
| DELETE | `/api/admin/review/wiki-data/character-aliases/:alias_id` | Legacy/direct delete character alias |

Editor PATCH behavior:

- Request bodies must be JSON objects.
- Canonical names are required for characters, skills, and items.
- Chapter references must be valid chapter IDs from the same novel.
- Alias, relationship, and cultivation payloads must be arrays of objects.
- Duplicate aliases and duplicate character-skill links are rejected before database commit where possible.
- Skill and item categories are normalized and restricted to supported category values.
- Relationship removals are staged by sending rows marked with `_deleted`.
- PATCH responses return the updated editor record shape.

The chapter search endpoint exists so the admin UI does not render huge chapter dropdowns for novels with hundreds or thousands of chapters.

### Wiki Edit Log Query Parameters

`GET /api/admin/review/wiki-data/novels/:novel_id/edit-log` supports:

| Parameter | Purpose |
| --- | --- |
| `search` | Search entity labels, field names, summaries, and old/new values |
| `entity_type` | Filter by entity/change context, for example `character`, `skill`, `item`, `alias`, `skill_alias`, `cultivation`, `character_skill`, or `character_item` |
| `change_type` | Filter by `added`, `updated`, or `removed` |
| `date_from` | Inclusive date lower bound, formatted as `YYYY-MM-DD` or ISO datetime |
| `date_to` | Inclusive date upper bound, formatted as `YYYY-MM-DD` or ISO datetime |
| `edited_by` | Filter by editor display name; currently usually `Admin` |
| `page` | Page number |
| `per_page` | Page size, capped by the backend |

Response shape:

```json
{
  "data": {
    "logs": [
      {
        "id": 1,
        "novel_id": 1,
        "entity_type": "alias",
        "entity_id": 10,
        "entity_label": "Meng Hao",
        "parent_entity_type": "character",
        "parent_entity_id": 1,
        "parent_entity_label": "Meng Hao",
        "change_type": "added",
        "field_name": "Alias",
        "old_value": null,
        "new_value": "Hao-ge",
        "summary": "Added alias to Meng Hao.",
        "edited_by": "Admin",
        "created_at": "2026-06-12T09:03:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 172,
      "total_pages": 18
    }
  },
  "error": null
}
```

## Public Wiki API

Public endpoints return approved records only and never expose full chapter text.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/wiki/novels` | List public novels |
| GET | `/api/wiki/novels/:novel_id` | Public novel overview |
| GET | `/api/wiki/novels/:novel_id/characters` | List approved characters |
| GET | `/api/wiki/characters/:character_id` | Approved character detail page |
| GET | `/api/wiki/novels/:novel_id/progression` | Novel-level approved progression/cultivation feed |
| GET | `/api/wiki/novels/:novel_id/skills` | List approved skills and techniques |
| GET | `/api/wiki/skills/:skill_id` | Approved skill page |
| GET | `/api/wiki/novels/:novel_id/items` | List approved items |
| GET | `/api/wiki/items/:item_id` | Approved item page |

## Future Search

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/search?novel_id=&q=` | Search approved wiki content |
