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

## Public Wiki Routes

- `/wiki/novels`: Novel library.
- `/wiki/novels/:novelId`: Selected novel overview.
- `/wiki/novels/:novelId/characters`: Character list for the selected novel.
- `/wiki/novels/:novelId/characters/:characterId`: Character detail page.

The public wiki opens on the novel library. Novel-specific navigation appears only after a novel is selected.
