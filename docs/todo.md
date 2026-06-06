# TODO

Living list for product and data-quality ideas discovered during testing.

## Near Term

- Smoke-test Wiki Data Editor saves against public wiki pages for characters, skills, and items.
- Add audit/edit history for canonical Wiki Data Editor changes.
- Consider reducing prop-heavy editor component calls after the current component split settles.
- Clean up backend wiki editor route/service boundaries if `admin_review.py` grows further.
- Add admin cleanup tools for repeated testing, such as clearing extraction runs/review data for a novel or chapter range.
- Improve duplicate review flow for names, aliases, progression values, metadata proposals, and relationship records.
- Add safeguards around book source replacement/reparse when approved wiki data or pending review data exists.
- Improve evidence matching so "View Full Context" finds paragraphs more reliably when AI evidence uses ellipses or stitched snippets.
- Add richer extraction diagnostics in the admin UI for failed chapters, including raw provider error details where safe.
- Decide whether approved/rejected review items should be hidden by default in chapter groups while still visible through filters.

## Later

- Add AI-generated public description synthesis for characters, skills, and items.
- Add a novel power-system profile with realms, synonyms, and ordering rules.
- Add genre/profile options for extraction prompts, starting with cultivation novels and later LitRPG.
- Improve canonical-name priority during merges, especially when a full personal name appears after a title or nickname.
- Add robust `.epub` and `.pdf` parsing.
- Add public organization/location/timeline pages after character/progression quality is stable.
