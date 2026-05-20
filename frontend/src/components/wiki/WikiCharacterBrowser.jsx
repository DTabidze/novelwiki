import React from "react";
import { chapterLabel, formatCultivationValue, formatNumber } from "../../utils/wikiFormat.js";

export default function WikiCharacterBrowser({ characters, novel, onSelectCharacter }) {
  const [activeLetter, setActiveLetter] = React.useState("All");
  const [searchTerm, setSearchTerm] = React.useState("");
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
  const sortedCharacters = [...characters].sort((first, second) => first.name.localeCompare(second.name));
  const filteredCharacters = sortedCharacters.filter((character) => {
    const firstLetter = (character.name || "?").trim().slice(0, 1).toUpperCase();
    const matchesLetter = activeLetter === "All" || firstLetter === activeLetter;
    const matchesSearch = character.name.toLowerCase().includes(searchTerm.trim().toLowerCase());

    return matchesLetter && matchesSearch;
  });
  const groupedCharacters = alphabet
    .map((letter) => ({
      letter,
      rows: filteredCharacters.filter(
        (character) => (character.name || "?").trim().slice(0, 1).toUpperCase() === letter
      ),
    }))
    .filter((group) => group.rows.length > 0);

  return (
    <article className="wiki-character-browser">
      <section className="wiki-cultivation-header">
        <div>
          <h1>Characters</h1>
          <p>{formatNumber(characters.length)} characters</p>
        </div>
        <div className="wiki-character-tools">
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search characters by name..."
          />
          <select
            value=""
            onChange={(event) => {
              const character = sortedCharacters.find((item) => item.id === Number(event.target.value));

              if (character) {
                onSelectCharacter(character);
              }
            }}
          >
            <option value="">Jump to character...</option>
            {sortedCharacters.map((character) => (
              <option key={character.id} value={character.id}>
                {character.name}
              </option>
            ))}
          </select>
        </div>
      </section>

      <nav className="wiki-alphabet-nav" aria-label="Filter characters by first letter">
        <button
          className={activeLetter === "All" ? "active" : ""}
          type="button"
          onClick={() => setActiveLetter("All")}
        >
          All
        </button>
        {alphabet.map((letter) => (
          <button
            className={activeLetter === letter ? "active" : ""}
            key={letter}
            type="button"
            onClick={() => setActiveLetter(letter)}
          >
            {letter}
          </button>
        ))}
      </nav>

      <section className="wiki-character-index">
        {filteredCharacters.length === 0 ? <p>No matching characters found.</p> : null}
        {groupedCharacters.map((group) => (
          <section className="wiki-cultivation-letter-group" key={group.letter}>
            <div className="wiki-cultivation-letter-heading character-heading">
              <h2>{group.letter}</h2>
            </div>
            <div className="wiki-character-rows">
              {group.rows.map((character) => {
                const cultivation = character.current_cultivation_level
                  ? formatCultivationValue(character.current_cultivation_level)
                  : "Unknown Cultivation";
                const position = character.current_position || "Unknown Position";

                return (
                  <button
                    className="wiki-character-row"
                    key={character.id}
                    type="button"
                    onClick={() => onSelectCharacter(character)}
                  >
                    <strong>{character.name}</strong>
                    <span>
                      {cultivation} <em>•</em> {position}
                    </span>
                    <small>First Appearance: {chapterLabel(character.first_appeared_chapter)}</small>
                    <span className="wiki-row-action">›</span>
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </section>
    </article>
  );
}
