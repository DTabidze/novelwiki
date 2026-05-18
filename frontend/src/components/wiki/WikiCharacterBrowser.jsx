import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatNumber } from "../../utils/wikiFormat.js";

export default function WikiCharacterBrowser({ characters, novel, onSelectCharacter }) {
  return (
    <article className="wiki-character-browser">
      <section className="wiki-library-header compact">
        <span className="wiki-novel-tag">{novel.title}</span>
        <h1>Characters</h1>
        <p>Browse approved characters for this novel.</p>
      </section>

      <section className="wiki-card">
        <div className="wiki-card-heading">
          <h2>All Characters</h2>
          <span>{formatNumber(characters.length)} approved</span>
        </div>
        {characters.length === 0 ? <p>No approved characters yet.</p> : null}
        <div className="wiki-character-browser-grid">
          {characters.map((character) => (
            <button
              className="wiki-character-browser-card"
              key={character.id}
              type="button"
              onClick={() => onSelectCharacter(character)}
            >
              <WikiAvatar name={character.name} size="small" />
              <div>
                <strong>{character.name}</strong>
                <span>{character.current_cultivation_level || character.current_position || "Character"}</span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </article>
  );
}
