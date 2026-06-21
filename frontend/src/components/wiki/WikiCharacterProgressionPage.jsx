import React from "react";
import { Link } from "react-router-dom";
import WikiProgressionView from "./WikiProgressionView.jsx";
import { WikiProgressionSkeleton } from "./WikiSkeletons.jsx";

function spoilerPreferenceKey(novel, character) {
  const novelId = novel?.id || character?.novel_id || character?.novel?.id || "global";

  return `wiki-spoiler-preference:${novelId}`;
}

function readSpoilerPreference(key) {
  if (typeof window === "undefined") {
    return { readChapter: "", revealAll: false };
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || "{}");

    return {
      readChapter: parsed.readChapter ? String(parsed.readChapter) : "",
      revealAll: Boolean(parsed.revealAll),
    };
  } catch (_error) {
    return { readChapter: "", revealAll: false };
  }
}

function writeSpoilerPreference(key, preference) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(preference));
  } catch (_error) {
    // Spoiler preferences are a convenience; the page should still work if storage is unavailable.
  }
}

export default function WikiCharacterProgressionPage({ character, isLoading = false, novel = null }) {
  const preferenceKey = React.useMemo(() => spoilerPreferenceKey(novel, character), [novel, character]);
  const [readChapter, setReadChapter] = React.useState("");
  const [chapterInput, setChapterInput] = React.useState("");
  const [revealAll, setRevealAll] = React.useState(false);
  const [revealedEventIds, setRevealedEventIds] = React.useState(() => new Set());

  React.useEffect(() => {
    const preference = readSpoilerPreference(preferenceKey);

    setReadChapter(preference.readChapter);
    setChapterInput(preference.readChapter);
    setRevealAll(preference.revealAll);
    setRevealedEventIds(new Set());
  }, [preferenceKey]);

  if (isLoading) {
    return <WikiProgressionSkeleton />;
  }

  if (!character) {
    return (
      <section className="wiki-empty-panel">
        <h2>Select a character</h2>
        <p>Choose a character to view their cultivation progression.</p>
      </section>
    );
  }

  const spoilerLimit = readChapter ? Number(readChapter) : null;

  function saveReadChapter(event) {
    event.preventDefault();

    const numericChapter = Number(chapterInput);
    const normalized = Number.isFinite(numericChapter) && numericChapter > 0
      ? String(Math.floor(numericChapter))
      : "";
    const nextPreference = { readChapter: normalized, revealAll: false };

    setReadChapter(normalized);
    setChapterInput(normalized);
    setRevealAll(false);
    setRevealedEventIds(new Set());
    writeSpoilerPreference(preferenceKey, nextPreference);
  }

  function revealEverySpoiler() {
    const nextPreference = { readChapter, revealAll: true };

    setRevealAll(true);
    setRevealedEventIds(new Set());
    writeSpoilerPreference(preferenceKey, nextPreference);
  }

  function protectProgression() {
    const nextPreference = { readChapter, revealAll: false };

    setRevealAll(false);
    setRevealedEventIds(new Set());
    writeSpoilerPreference(preferenceKey, nextPreference);
  }

  function revealEvent(eventId) {
    setRevealedEventIds((current) => {
      const next = new Set(current);
      next.add(eventId);
      return next;
    });
  }

  return (
    <article className="wiki-cultivation-page">
      <section className="wiki-library-header compact">
        <h1>Cultivation Timeline</h1>
        <p>
          Chronological record of cultivation breakthroughs and position advancements of{" "}
          <Link className="wiki-inline-link" to={`/wiki/novels/${novel?.id || character.novel_id}/characters/${character.id}`}>
            {character.name}
          </Link>
          .
        </p>
      </section>

      <section className="wiki-spoiler-limit-card">
        <div>
          <strong>Spoiler protection</strong>
          <span>
            {revealAll
              ? "All progression entries are visible."
              : readChapter
                ? `Showing progression up to Chapter ${readChapter}.`
                : "Progression entries are covered until you set a read chapter or reveal them."}
          </span>
        </div>
        <form onSubmit={saveReadChapter}>
          <label>
            Read up to
            <input
              min="1"
              type="number"
              value={chapterInput}
              placeholder="Chapter"
              onChange={(event) => setChapterInput(event.target.value)}
            />
          </label>
          <button className="wiki-outline-link" type="submit">Apply</button>
          {revealAll ? (
            <button className="wiki-outline-link" type="button" onClick={protectProgression}>
              Cover spoilers
            </button>
          ) : (
            <button className="wiki-outline-link" type="button" onClick={revealEverySpoiler}>
              Reveal all
            </button>
          )}
        </form>
      </section>

      <WikiProgressionView
        events={character.progression_events || []}
        revealedEventIds={revealedEventIds}
        revealAllSpoilers={revealAll}
        spoilerLimit={spoilerLimit}
        onRevealEvent={revealEvent}
      />
    </article>
  );
}
