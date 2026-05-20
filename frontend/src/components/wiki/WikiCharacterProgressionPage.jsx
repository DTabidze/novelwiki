import React from "react";
import WikiProgressionView from "./WikiProgressionView.jsx";

export default function WikiCharacterProgressionPage({ character }) {
  if (!character) {
    return (
      <section className="wiki-empty-panel">
        <h2>Loading progression</h2>
        <p>The character progression page will appear once the approved wiki data loads.</p>
      </section>
    );
  }

  return (
    <article className="wiki-cultivation-page">
      <section className="wiki-library-header compact">
        <span className="wiki-novel-tag">{character.name}</span>
        <h1>Cultivation Timeline</h1>
        <p>Chronological record of cultivation breakthroughs and position advancements.</p>
      </section>

      <WikiProgressionView events={character.progression_events || []} />
    </article>
  );
}
