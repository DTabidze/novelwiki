import React from "react";
import WikiProgressionView from "./WikiProgressionView.jsx";
import { WikiProgressionSkeleton } from "./WikiSkeletons.jsx";

export default function WikiCharacterProgressionPage({ character, isLoading = false }) {
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
