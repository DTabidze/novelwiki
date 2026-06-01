# Frontend

React app for the admin upload/review flow and approved public wiki pages.

## Folders

- `src/main.jsx`: React entrypoint. Mounts the app and router.
- `src/App.jsx`: Top-level app state and routes.
- `src/api.js`: Small API client helpers for calling Flask.
- `src/admin/`: Admin application shell, novel library, workspace pages, review queue, extraction UI, and admin-only components.
- `src/admin/styles/`: Admin CSS split by domain.
- `src/components/wiki/`: Public wiki UI pieces.
- `src/utils/`: Small frontend utility functions.

## Current Shape

The current MVP has two top-level views:

- Admin: manage novel workspaces, upload books, inspect chapters, run extraction, review extracted records.
- Wiki: browse approved novels, characters, cultivation progression, skills, and items.

Public wiki pages only show reviewed data returned by `/api/wiki/*`.

## Admin UI

The admin UI is an operational/editorial workspace. It supports:

- Creating and editing novel workspaces.
- Uploading book/source files.
- Inspecting book ingestion, parsed chapters, pending counts, and warnings.
- Running AI extraction for a single chapter, chapter range, full book, or continuation scope.
- Viewing extraction run history with explicit requested/completed/failed/canceled ranges.
- Canceling runs without deleting completed review output.
- Reviewing extracted records in a chapter-collapsible queue.
- Opening nearby evidence context.
- Editing review proposals before approval.
- Approving or rejecting records.
- Merging duplicate character records.
- Reviewing character metadata proposals as field-level updates.

Review cards are tagged by entity type so mixed chapter review is easier to scan. Metadata proposal cards show old value, proposed value, raw value, normalized value, confidence, warnings, and evidence when available. The edit modal changes only the proposal being reviewed and does not automatically approve it.

## Public Wiki Routes

- `/wiki/novels`: Novel library.
- `/wiki/novels/:novelId`: Selected novel overview.
- `/wiki/novels/:novelId/characters`: Character list for the selected novel.
- `/wiki/novels/:novelId/characters/:characterId`: Character detail page.
- `/wiki/novels/:novelId/characters/:characterId/progression`: Full progression page for one character.
- `/wiki/novels/:novelId/cultivation`: Novel-level cultivation/progression page.
- `/wiki/novels/:novelId/skills`: Skill list.
- `/wiki/novels/:novelId/skills/:skillId`: Skill detail page.
- `/wiki/novels/:novelId/items`: Item list.
- `/wiki/novels/:novelId/items/:itemId`: Item detail page.

The public wiki opens on the novel library. Novel-specific navigation appears only after a novel is selected.

## Public Wiki Pages

The public character page is data-focused. It shows:

- Header/profile area.
- Quick facts from approved character fields.
- About/description.
- Aliases.
- Current cultivation summary with a link to full progression.
- Current position and metadata such as age, gender, race/species, origin, affiliation, status, and latest title when available.
- Skills and items summaries.
- Subtle/collapsed life event information.
- Short evidence highlights.

The character page intentionally does not show the full progression timeline. That belongs on the character progression page.

Skill and item pages show approved relationships back to characters when those relationships exist.

## Formatting Helpers

`src/utils/wikiFormat.js` contains frontend display formatting helpers for chapter labels, relationship labels, cultivation values, metadata values, initials, dates, and numbers.
