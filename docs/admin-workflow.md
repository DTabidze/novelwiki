# Admin Workflow

NovelWiki admin is an editorial operations workspace. Its job is to move source text through AI extraction into reviewed public wiki data.

```text
Novel workspace
  -> Book source files
  -> Parsed chapters
  -> Extraction runs
  -> Review Queue
  -> Approved public wiki data
  -> Wiki Data Editor corrections
```

## Novel Library

The admin library lists novel workspaces. A workspace stores novel profile metadata such as title, author, description, cover, and status.

Use the library to:

- create a novel workspace
- search existing workspaces
- open a novel workspace
- edit novel profile details

## Books

Books are source-file/volume management. This page should stay focused on ingestion, not wiki data review.

Use Books to:

- upload source files
- inspect source filename and parsing status
- view chapter counts
- replace source files
- reparse a book when needed
- open parsed chapters

Replacing a source file does not automatically reparse. Reparsing is destructive for that book's parsed chapters and should be treated carefully once review data exists.

## Chapters

Chapters are parsed source units. They are the smallest normal extraction unit and the main narrative ordering used by the Review Queue.

Use Chapters to:

- inspect parsed chapter titles/previews
- see pending review and warning counts
- confirm parsing quality before extraction

## Extraction

Extraction runs convert chapter text into reviewable wiki proposals.

Supported scopes:

- single chapter
- chapter range
- full book
- continuation/resume range

Run history is intentionally historical. If a full-book run fails at Chapter 62, continuing from Chapter 62 creates a new run instead of mutating the original failed run.

Run cards should make these facts explicit:

- requested range
- completed range
- current chapter
- failed or canceled chapter
- records created
- warnings
- duration or error

Canceling a run means "stop future work." It does not delete review items already created from completed chapters. Deleting generated review data should remain a separate destructive action.

## Review Queue

The Review Queue is the moderation layer between AI output and canonical public wiki data.

The workflow is:

```text
scan chapters -> select item -> inspect evidence -> edit if needed -> approve/reject
```

Important behavior:

- Filters apply before grouping.
- Review items are grouped by chapter.
- Chapter groups can be collapsed/expanded.
- The selected item opens in the right-side inspector.
- Previous/Next moves through the current filtered/sorted queue.
- Approving or rejecting an item should keep the reviewer near their current position.

The inspector shows:

- proposal type
- title/status/confidence/chapter
- proposed data
- evidence
- AI notes
- warnings
- edit action
- approve/reject actions

The "View Full Context" action opens nearby paragraphs around the evidence snippet. It does not show the full chapter by default.

The "Edit" action modifies only the proposal being reviewed. It does not edit the canonical entity and does not automatically approve the item.

## Wiki Data Editor

The Wiki Data Editor edits canonical approved wiki data that is already eligible for public wiki pages. It is separate from the Review Queue.

Use the Review Queue when:

- AI created a pending proposal
- the fact has not been approved yet
- the reviewer is deciding whether to approve, reject, or adjust a proposal

Use the Wiki Data Editor when:

- an approved/public fact needs correction
- a canonical character, skill, item, alias, cultivation breakthrough, or relationship needs to be added manually
- an approved relationship needs better chapter/evidence/notes metadata

Current editor surfaces:

- Characters
- Skills
- Items

Character editing includes:

- basic profile fields
- first mentioned/first appeared chapter references
- aliases, including one primary alias
- cultivation breakthrough history
- character-skill links
- character-item links
- evidence read-only view
- admin notes and metadata history

Skill editing includes:

- name, category, description, and admin notes
- skill aliases
- characters attached to the skill
- evidence read-only view

Item editing includes:

- name, category, description, and admin notes
- characters attached to the item
- evidence read-only view

The editor uses a search/drawer browser for large entity lists so the active editor panel keeps most of the workspace width. URLs preserve the selected entity, record, and editor section, for example:

```text
/admin/novels/1/editor?entity=characters&character=1&section=aliases
```

Chapter references use a reusable chapter reference picker. Admins type a chapter number or search chapter title/number; the backend resolves and saves the actual chapter ID. This avoids rendering thousands of chapter options in a dropdown.

Save behavior:

- Edits stay local until Save Changes is confirmed.
- Save confirmation summarizes updated, added, and removed records.
- Switching records with unsaved changes opens a warning modal with the same change summary.
- Deleting aliases, cultivation rows, skills, items, or character relationships is staged locally and only persisted on Save Changes.
- Cancel resets the current record draft to the last loaded canonical data.

The editor should not expose `approved` as a normal editable status because every record loaded here is already canonical approved wiki data.

## Review Status Rules

Reviewable records use:

- `pending`
- `approved`
- `rejected`

Public wiki endpoints return approved records only.

Rejected records usually remain historical admin data. For progression dedupe, rejected rows do not block later proposals for the same character/value because the later proposal may have stronger evidence.

## Public Wiki

The public wiki is read-only for reviewed facts. It should not expose full chapter text or unreviewed AI output.

Public pages include:

- novel library
- novel overview
- character browser/detail
- character progression
- novel progression/cultivation overview
- skills
- items
