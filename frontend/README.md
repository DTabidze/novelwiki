# Frontend

React app for the admin upload/review flow and approved public wiki pages.

## Folders

- `src/api/`: Small API client functions for calling Flask.
- `src/components/`: Reusable UI pieces.
- `src/pages/`: Page-level views such as novel overview and character pages.

## Current Shape

The current MVP has two top-level views:

- Admin: upload novels, inspect chapters, run extraction, review extracted records.
- Wiki: browse approved novels, characters, skills, and items.

Public wiki pages only show reviewed data returned by `/api/wiki/*`.
