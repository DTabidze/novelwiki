# Frontend

React app for the admin upload/review flow and approved public wiki pages.

## Folders

- `src/main.jsx`: React entrypoint. Mounts the app and router.
- `src/App.jsx`: Top-level app state and routes.
- `src/api.js`: Small API client helpers for calling Flask.
- `src/components/admin/`: Admin review UI pieces.
- `src/components/wiki/`: Public wiki UI pieces.
- `src/utils/`: Small frontend utility functions.

## Current Shape

The current MVP has two top-level views:

- Admin: upload novels, inspect chapters, run extraction, review extracted records.
- Wiki: browse approved novels, characters, cultivation progression, skills, and items.

Public wiki pages only show reviewed data returned by `/api/wiki/*`.

## Admin UI

The admin UI is temporary but functional. It supports:

- Uploading `.txt` novels.
- Inspecting parsed chapter metadata and previews.
- Running AI extraction for a single chapter.
- Running AI extraction for selected chapters or the whole book.
- Reviewing extracted records in one chapter-sorted list.
- Hiding approved and/or rejected cards while reviewing.
- Editing extracted fields before saving.
- Approving or rejecting records.
- Merging duplicate character records.
- Reviewing character metadata proposals as field-level updates.

Review cards are tagged by entity type so mixed chapter review is easier to scan. Metadata proposal cards show old value, proposed value, raw value, normalized value, confidence, warnings, and evidence when available.

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
