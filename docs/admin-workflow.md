# Admin Workflow

NovelWiki admin is an editorial operations workspace. Its job is to move source text through AI extraction into reviewed public wiki data.

```text
Novel workspace
  -> Book source files
  -> Parsed chapters
  -> Extraction runs
  -> Review Queue
  -> Approved public wiki data
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
