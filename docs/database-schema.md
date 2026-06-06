# Database Schema

SQLite is enough for local MVP development. Move to PostgreSQL later when multiple writers, hosted production, advanced search, or larger concurrent usage become real requirements.

The current schema is managed with `db.create_all()` plus `ensure_development_schema()` for local development convenience. That is not a production migration system.

## Core Workspace Tables

### novels

Stores one novel workspace.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| title | text | Display title |
| author | text nullable | Author shown in admin and public wiki |
| description | text nullable | Novel description |
| cover_image_url | text nullable | Optional cover image URL |
| original_filename | text | Legacy/original upload filename; may be empty for workspace-created novels |
| file_type | text | Source type hint |
| status | text | ready, processing, failed, etc. |
| error_message | text nullable | Last processing/extraction error |
| created_at | datetime | Creation time |
| updated_at | datetime | Last change |

### books

Stores one source volume/book inside a novel workspace.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| number | integer | Book/volume number, unique per novel |
| title | text | Book title |
| source_filename | text nullable | Stored source file name |
| parsing_status | text | parsed, source_replaced, failed, etc. |
| extraction_status | text | not_started, running, completed, failed |
| created_at | datetime | Row creation time |
| uploaded_at | datetime | Last source upload time |

### chapters

Stores parsed chapter text and order.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| book_id | integer foreign key nullable | Links to books |
| chapter_number | integer | Sort order inside the book |
| title | text | Chapter title |
| content | text | Raw source chapter text, admin/backend only |
| character_count | integer | Raw character count for verification |
| created_at | datetime | Created time |

`book_id + chapter_number` is unique.

## Extraction Run Tables

### extraction_runs

Stores a historical extraction run. Failed/canceled runs are not mutated into resumed runs; continuation creates a new run.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| book_id | integer foreign key nullable | Book scope if applicable |
| chapter_start | integer nullable | Requested start chapter |
| chapter_end | integer nullable | Requested end chapter |
| scope_type | text | single_chapter, chapter_range, full_book, continue, etc. |
| status | text | queued, running, completed, failed, canceled |
| total_chapters | integer | Requested chapter count |
| completed_chapters | integer | Successfully completed chapters in this run |
| failed_chapters | integer | Failed chapter count |
| current_chapter_id | integer nullable | Current/last active chapter |
| created_records_count | integer | Records created by this run |
| warning_count | integer | Review warning count associated with run output |
| summary_json | text nullable | Aggregated extraction summary |
| error_message | text nullable | Failure/cancel reason |
| started_at | datetime nullable | Start time |
| finished_at | datetime nullable | End time |
| created_at | datetime | Row creation time |

### extraction_run_chapters

Stores per-chapter status for an extraction run.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| extraction_run_id | integer foreign key | Links to extraction_runs |
| chapter_id | integer foreign key | Links to chapters |
| status | text | pending, running, completed, failed, skipped, canceled |
| records_created | integer | Records created for that chapter |
| warning_count | integer | Review warnings for that chapter |
| summary_json | text nullable | Per-chapter summary |
| error_message | text nullable | Per-chapter failure reason |
| started_at | datetime nullable | Start time |
| finished_at | datetime nullable | End time |
| created_at | datetime | Row creation time |
| updated_at | datetime | Last update time |

## Reviewable Wiki Data

Most extracted wiki data includes `review_status` and `admin_notes` through `ReviewMixin`.

Review statuses:

- `pending`
- `approved`
- `rejected`

Public APIs return approved records only.

### characters

Stores generated character wiki pages and approved/current summary fields.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Character name |
| description | text nullable | Short generated summary |
| first_mentioned_chapter_id | integer nullable | First textual mention |
| first_appeared_chapter_id | integer nullable | First direct appearance |
| first_seen_chapter_id | integer nullable | Legacy/general first-seen field |
| age_text | text nullable | Reviewed age text |
| gender | text nullable | Reviewed gender |
| race_or_species | text nullable | Reviewed or assumed species |
| race_or_species_source | text nullable | extracted or implicit_default |
| race_or_species_confidence | text nullable | confirmed or assumed |
| origin | text nullable | Reviewed origin |
| faction_or_affiliation | text nullable | Reviewed affiliation |
| status | text nullable | Life status only |
| titles | text nullable | Reviewed durable titles |
| current_cultivation_level | text nullable | Current value derived from progression/review behavior |
| current_position | text nullable | Role, title, job, disciple status |
| current_class_rank | text nullable | Non-cultivation class/rank |
| current_power_rank | text nullable | Non-cultivation power rank |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

### character_aliases

Stores alternate names for a character.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| character_id | integer foreign key | Links to characters |
| alias | text | Alternate name or title |
| first_seen_chapter_id | integer nullable | First chapter where alias is seen |
| evidence | text nullable | Short supporting note |
| is_primary | boolean | One alias can be marked as the primary/display alias |
| created_at | datetime | Created time |

### character_metadata_proposals

Stores field-level metadata proposals for existing characters.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| chapter_id | integer foreign key | Evidence chapter |
| field_name | text | Character field being proposed |
| old_value | text nullable | Existing field value |
| raw_proposed_value | text nullable | Raw extracted value |
| proposed_value | text | Display proposed value |
| normalized_value | text nullable | Normalized value used for dedupe |
| confidence_score | float nullable | Metadata confidence |
| extraction_reason | text nullable | Why the proposal was created |
| auto_approved | boolean | Whether safe auto-approval applied |
| evidence | text nullable | Evidence snippet |
| review_warnings | text nullable | Newline-separated warnings |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |
| updated_at | datetime | Last update |

### character_progression_events

Tracks cultivation levels, rank changes, positions, and other durable progression.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| chapter_id | integer foreign key | Evidence chapter |
| progression_type | text | cultivation_level, position, class_rank, power_rank |
| old_value | text nullable | Previous value if known |
| new_value | text | Confirmed proposed/current value |
| description | text nullable | Short explanation |
| review_warnings | text nullable | Newline-separated warnings |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

Progression dedupe ignores rejected rows so stronger later evidence can create a fresh pending proposal.

### character_life_events

Tracks major reviewed life/status events.

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
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

### skills / items

Store approved/pending/rejected skills, techniques, items, weapons, and artifacts.

Shared shape:

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| name | text | Skill/item name |
| category | text nullable | Type/category |
| description | text nullable | Generated description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

Skill aliases:

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| skill_id | integer foreign key | Links to skills |
| alias | text | Alternate skill name |
| first_seen_chapter_id | integer nullable | First chapter where alias is seen |
| evidence | text nullable | Short supporting note |
| created_at | datetime | Created time |

`skill_id + alias` is unique.

Character-skill relationships:

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| skill_id | integer foreign key | Links to skills |
| chapter_id | integer foreign key | First known chapter/evidence chapter |
| relationship_type | text | Internal legacy field normalized to `has` |
| description | text nullable | Short context/description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

The canonical wiki model treats this as "character has skill." Extraction verbs such as learned, acquired, studied, used, knows, or teaches should not create separate public/editor relationships. `character_id + skill_id` is unique.

Character-item relationships:

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| character_id | integer foreign key | Links to characters |
| item_id | integer foreign key | Links to items |
| chapter_id | integer foreign key | First known chapter/evidence chapter |
| relationship_type | text | Relationship label such as ownership/possession/status if used |
| description | text nullable | Short context/description |
| review_status | text | pending, approved, rejected |
| admin_notes | text nullable | Admin-only notes |
| created_at | datetime | Created time |

There is currently no item alias table.

### wiki_events

Stores timeline events. Timeline extraction is currently de-emphasized while characters, metadata, and progression quality are refined.

### wiki_evidence

Keeps evidence separate so generated facts are traceable.

| Column | Type | Notes |
| --- | --- | --- |
| id | integer primary key | Internal ID |
| novel_id | integer foreign key | Links to novels |
| chapter_id | integer foreign key | Source chapter |
| entity_type | text | character, skill, item, event, progression, life_event, etc. |
| entity_id | integer | ID in the entity table |
| evidence_text | text | Short supporting text |
| created_at | datetime | Created time |

## Beginner-Friendly Notes

- Store uncertain values as pending review records first.
- Keep evidence for every generated fact.
- Avoid over-normalizing cultivation systems until real data patterns justify it.
- Treat canceling extraction separately from deleting generated review data.
- Use the Wiki Data Editor for approved canonical corrections, not for pending proposal review.
- Add full-text search later after the review pipeline stabilizes.
