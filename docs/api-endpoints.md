# REST API Endpoints

Use `/api` as the API prefix.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check that the backend is running |

## Admin

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/admin/novels/upload` | Upload a `.txt` novel file |
| GET | `/api/admin/novels` | List uploaded novels with processing status |
| GET | `/api/admin/novels/:id/chapters` | List chapters for admin verification |
| GET | `/api/admin/novels/:id/extracted-data` | Load extracted review records |
| POST | `/api/admin/novels/:id/process` | Run placeholder processing |
| POST | `/api/admin/novels/:id/chapters/:chapter_id/extract` | Run AI extraction for one chapter |

## Admin Review

| Method | Path | Purpose |
| --- | --- | --- |
| PATCH | `/api/admin/review/:entity_type/:id` | Save, approve, or reject an extracted record |
| POST | `/api/admin/review/characters/:source_id/merge` | Merge one character into another |

Supported review entity types:

- `characters`
- `skills`
- `items`
- `events`
- `progression_events`
- `life_events`

## Public Wiki API

Public endpoints return approved records only and never expose full chapter text.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/wiki/novels` | List public novels |
| GET | `/api/wiki/novels/:id` | Public novel overview |
| GET | `/api/wiki/novels/:id/characters` | List approved characters |
| GET | `/api/wiki/characters/:id` | Approved character page |
| GET | `/api/wiki/novels/:id/skills` | List approved skills and techniques |
| GET | `/api/wiki/skills/:id` | Approved skill page |
| GET | `/api/wiki/novels/:id/items` | List approved items |
| GET | `/api/wiki/items/:id` | Approved item page |

## Future Search

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/search?novel_id=&q=` | Search approved wiki content |

## Response Style

Keep responses predictable:

```json
{
  "data": {},
  "error": null
}
```

For lists:

```json
{
  "data": [],
  "error": null
}
```
