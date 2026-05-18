import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import { chapterLabel, firstDescriptionChunk, relationshipLabel } from "../../utils/wikiFormat.js";

export default function WikiCharacterDetail({ character, relatedCharacters = [], onSelectRelated }) {
  if (!character) {
    return (
      <section className="wiki-empty-panel">
        <h2>Select a character</h2>
        <p>Choose an approved character from the sidebar to view their public wiki page.</p>
      </section>
    );
  }

  const displayDescription = firstDescriptionChunk(character.description);
  const progressionEvents = [...(character.progression_events || [])].sort((first, second) => {
    const firstChapter = first.chapter ? first.chapter.chapter_number : 0;
    const secondChapter = second.chapter ? second.chapter.chapter_number : 0;
    return secondChapter - firstChapter;
  });
  const currentProgression = progressionEvents.find(
    (event) =>
      character.current_cultivation_level &&
      event.new_value &&
      event.new_value.toLowerCase() === character.current_cultivation_level.toLowerCase()
  );
  const shownRelatedCharacters = relatedCharacters
    .filter((related) => related.id !== character.id)
    .slice(0, 3);

  return (
    <article className="wiki-character-page">
      <section className="wiki-hero-card">
        <div className="wiki-portrait">
          <WikiAvatar name={character.name} />
        </div>

        <div className="wiki-hero-main">
          <div className="wiki-title-row">
            <h1>{character.name}</h1>
            <span className="wiki-title-mark">Qi</span>
          </div>

          <div className="wiki-fact-grid">
            <div className="wiki-fact">
              <span className="wiki-fact-icon">C</span>
              <div>
                <small>Current Cultivation</small>
                <strong>{character.current_cultivation_level || "Unknown"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">P</span>
              <div>
                <small>Current Position</small>
                <strong>{character.current_position || "Unknown"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">B</span>
              <div>
                <small>First Mentioned</small>
                <strong>{chapterLabel(character.first_mentioned_chapter)}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">A</span>
              <div>
                <small>Aliases</small>
                <strong>
                  {character.aliases && character.aliases.length > 0
                    ? character.aliases.map((alias) => alias.alias).join(", ")
                    : "N/A"}
                </strong>
              </div>
            </div>
          </div>

          {displayDescription ? <p className="wiki-description">{displayDescription}</p> : null}
        </div>
      </section>

      <section className="wiki-content-grid">
        <div className="wiki-card wiki-progression-card">
          <h2>Cultivation Progression</h2>
          {progressionEvents.length === 0 ? <p>No approved progression yet.</p> : null}
          <div className="wiki-timeline">
            {progressionEvents.map((event) => {
              const isCurrent = currentProgression ? currentProgression.id === event.id : false;

              return (
                <article className={isCurrent ? "wiki-timeline-row active" : "wiki-timeline-row"} key={event.id}>
                  <span className="wiki-timeline-dot" />
                  <div>
                    <small>{chapterLabel(event.chapter)}</small>
                    <strong>{event.new_value}</strong>
                    {event.old_value ? <p>From {event.old_value}</p> : null}
                  </div>
                  {isCurrent ? <span className="wiki-stage-pill">Current Stage</span> : null}
                </article>
              );
            })}
          </div>
        </div>

        <div className="wiki-side-stack">
          <section className="wiki-card">
            <h2>Skills</h2>
            {character.skills && character.skills.length > 0 ? (
              character.skills.map((relationship) => (
                <article className="wiki-skill-row" key={relationship.id}>
                  <span className="wiki-skill-icon">F</span>
                  <div>
                    <strong>{relationship.skill ? relationship.skill.name : "Unknown skill"}</strong>
                    <p>{relationshipLabel(relationship)}</p>
                  </div>
                </article>
              ))
            ) : (
              <p>No approved skills yet.</p>
            )}
          </section>

          <section className="wiki-card">
            <h2>Related Characters</h2>
            {shownRelatedCharacters.length === 0 ? <p>No related characters yet.</p> : null}
            {shownRelatedCharacters.map((related) => (
              <button
                className="wiki-related-row"
                key={related.id}
                type="button"
                onClick={() => onSelectRelated(related)}
              >
                <WikiAvatar name={related.name} size="small" />
                <span>{related.name}</span>
                <small>{related.current_cultivation_level || related.current_position || ""}</small>
              </button>
            ))}
          </section>
        </div>
      </section>
    </article>
  );
}
