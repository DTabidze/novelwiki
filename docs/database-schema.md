# First Database Schema

SQLite is enough for the MVP. It is simple, local, fast, and beginner-friendly.

Move to PostgreSQL later when you need multiple writers, hosted production scaling, advanced search, or larger concurrent usage.

## Tables

### novels

Stores one uploaded novel.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| title | text | Display title |
| original_filename | text | Uploaded file name |
| file_type | text | txt, epub, docx |
| status | text | uploaded, processing, ready, failed |
| created_at | datetime | Upload time |
| updated_at | datetime | Last change |

### chapters

Stores chapter text and order.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| chapter_number | integer | Sort order |
| title | text | Chapter title if found |
| content | text | Chapter text |
| created_at | datetime | Created time |

### characters

Stores generated character wiki pages.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Character name |
| age | text nullable | Keep as text because novels are messy |
| race_species | text nullable | Human, demon, elf, etc. |
| description | text nullable | Short generated summary |
| first_seen_chapter_id | integer nullable | First detected chapter |

### character_progression_events

Tracks level-ups, rank changes, and gained abilities.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| character_id | integer foreign key | Links to characters |
| chapter_id | integer foreign key | Evidence chapter |
| event_type | text | level_up, skill_gain, item_gain, rank_change |
| old_value | text nullable | Previous rank if known |
| new_value | text nullable | New rank/skill/item |
| evidence | text | Short quote or paraphrase from text |

### skills

Stores techniques, powers, and abilities.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Skill or technique name |
| category | text nullable | technique, spell, passive, class skill |
| description | text nullable | Generated description |

### items

Stores important items, weapons, and artifacts.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Item name |
| category | text nullable | weapon, artifact, pill, armor |
| description | text nullable | Generated description |

### wiki_evidence

Keeps evidence separate so generated facts are traceable.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| chapter_id | integer foreign key | Source chapter |
| entity_type | text | character, skill, item, event |
| entity_id | integer | ID in that entity table |
| evidence_text | text | Short supporting text |

## Beginner-Friendly Notes

- Store uncertain values as text at first.
- Keep evidence for every generated fact.
- Avoid over-normalizing cultivation systems until you see real data patterns.
- Add full-text search later after the basic CRUD flow works.

