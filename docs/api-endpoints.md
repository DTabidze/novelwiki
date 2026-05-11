# First REST API Endpoints

Use `/api` as the API prefix.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check that the backend is running |

## Admin

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/admin/novels` | Upload a novel file |
| GET | `/api/admin/novels` | List uploaded novels with processing status |
| POST | `/api/admin/novels/:id/process` | Start or rerun processing |

## User-Facing Novel API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/novels` | List public novels |
| GET | `/api/novels/:id` | Novel overview |
| GET | `/api/novels/:id/chapters` | Chapter list |
| GET | `/api/novels/:id/timeline` | Important events by chapter |

## Wiki Entity API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/novels/:id/characters` | List characters |
| GET | `/api/characters/:id` | Character page |
| GET | `/api/novels/:id/skills` | List skills and techniques |
| GET | `/api/skills/:id` | Skill page |
| GET | `/api/novels/:id/items` | List items |
| GET | `/api/items/:id` | Item page |

## Search

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/search?novel_id=&q=` | Search generated wiki content |

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

