# Database Schema

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
| error_message | text nullable | Last processing error |
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
| character_count | integer | Raw character count for verification |
| created_at | datetime | Created time |

### characters

Stores generated character wiki pages. Public API shows only approved records.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Character name |
| description | text nullable | Short generated summary |
| first_mentioned_chapter_id | integer nullable | First chapter where the character is mentioned |
| first_appeared_chapter_id | integer nullable | First chapter where the character appears directly |
| first_seen_chapter_id | integer nullable | Legacy/general first-seen field |
| current_cultivation_level | text nullable | Raw current level from extraction; public view derives from approved progression |
| current_position | text nullable | Current role, title, occupation, or organization position |
| current_class_rank | text nullable | Generic class/rank value for non-cultivation systems |
| current_power_rank | text nullable | Generic power rank value |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### character_aliases

Stores alternate names for a character.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| character_id | integer foreign key | Links to characters |
| alias | text | Alternate name or title |
| first_seen_chapter_id | integer nullable | First chapter where the alias is seen |
| evidence | text nullable | Short supporting note |

### character_progression_events

Tracks cultivation levels, rank changes, positions, and other power/status progression.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| chapter_id | integer foreign key | Evidence chapter |
| progression_type | text | cultivation_level, position, class_rank, power_rank |
| old_value | text nullable | Previous rank if known |
| new_value | text | New confirmed value |
| description | text nullable | Short description of the change |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### character_life_events

Tracks major reviewed life/status events such as death, resurrection, marriage, exile, or similar durable states.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| chapter_id | integer foreign key | Evidence chapter |
| event_type | text | death, resurrection, marriage, exile, etc. |
| description | text nullable | What happened |
| reason | text nullable | Cause or context |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### skills

Stores techniques, powers, and abilities.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Skill or technique name |
| category | text nullable | technique, spell, passive, class skill |
| description | text nullable | Generated description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### skill_aliases

Stores alternate names for a skill.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| skill_id | integer foreign key | Links to skills |
| alias | text | Alternate skill name |
| first_seen_chapter_id | integer nullable | First chapter where the alias is seen |
| evidence | text nullable | Short supporting note |

### items

Stores important items, weapons, and artifacts.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Item name |
| category | text nullable | weapon, artifact, pill, armor |
| description | text nullable | Generated description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### wiki_events

Stores timeline events. Timeline extraction is currently de-emphasized for the MVP while characters and progression are refined.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| chapter_id | integer foreign key nullable | Source chapter |
| event_type | text | Event category |
| title | text | Event title |
| description | text nullable | Event description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only review notes |

### wiki_evidence

Keeps evidence separate so generated facts are traceable.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| chapter_id | integer foreign key | Source chapter |
| entity_type | text | character, skill, item, event, progression, life_event |
| entity_id | integer | ID in that entity table |
| evidence_text | text | Short supporting text |

## Beginner-Friendly Notes

- Store uncertain values as text at first.
- Keep evidence for every generated fact.
- Avoid over-normalizing cultivation systems until you see real data patterns.
- Add full-text search later after the basic CRUD flow works.
