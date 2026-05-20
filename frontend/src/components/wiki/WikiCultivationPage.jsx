import React from "react";
import { formatNumber, splitCultivationValue } from "../../utils/wikiFormat.js";

export default function WikiCultivationPage({
  characters,
  novel,
  onSelectCharacterProgression,
  progressionEvents,
}) {
  const [activeLetter, setActiveLetter] = React.useState("All");
  const [realmFilter, setRealmFilter] = React.useState("All");
  const [searchTerm, setSearchTerm] = React.useState("");
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

  function latestCultivationFor(character) {
    const currentLevel = character.current_cultivation_level;
    const characterEvents = progressionEvents
      .filter((event) => event.character_id === character.id)
      .filter((event) => event.progression_type === "cultivation_level");

    if (currentLevel) {
      return currentLevel;
    }

    if (characterEvents.length === 0) {
      return "";
    }

    return characterEvents[0].new_value || "";
  }

  const characterRows = characters
    .filter((character) => progressionEvents.some((event) => event.character_id === character.id))
    .map((character) => {
      const cultivation = splitCultivationValue(latestCultivationFor(character));

      return {
        character,
        firstLetter: (character.name || "?").trim().slice(0, 1).toUpperCase(),
        realm: cultivation.realm,
        realmKey: cultivation.realm.toLowerCase(),
        stage: cultivation.stage,
      };
    })
    .sort((first, second) => first.character.name.localeCompare(second.character.name));

  const realmOptions = [...new Set(characterRows.map((row) => row.realm))].sort((first, second) =>
    first.localeCompare(second)
  );
  const filteredRows = characterRows.filter((row) => {
    const matchesLetter = activeLetter === "All" || row.firstLetter === activeLetter;
    const matchesRealm = realmFilter === "All" || row.realmKey === realmFilter;
    const matchesSearch = row.character.name.toLowerCase().includes(searchTerm.trim().toLowerCase());

    return matchesLetter && matchesRealm && matchesSearch;
  });
  const groupedRows = alphabet
    .map((letter) => ({
      letter,
      rows: filteredRows.filter((row) => row.firstLetter === letter),
    }))
    .filter((group) => group.rows.length > 0);

  return (
    <article className="wiki-cultivation-page">
      <section className="wiki-cultivation-header">
        <div>
          <h1>Cultivation</h1>
          <p>{formatNumber(characterRows.length)} characters</p>
        </div>
        <div className="wiki-cultivation-tools">
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search characters..."
          />
          <select value={realmFilter} onChange={(event) => setRealmFilter(event.target.value)}>
            <option value="All">Filter by realm</option>
            {realmOptions.map((realm) => (
              <option key={realm} value={realm.toLowerCase()}>
                {realm}
              </option>
            ))}
          </select>
        </div>
      </section>

      <nav className="wiki-alphabet-nav" aria-label="Filter cultivation characters by first letter">
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

      <section className="wiki-cultivation-index">
        {filteredRows.length === 0 ? <p>No matching characters found.</p> : null}
        {groupedRows.map((group) => (
          <section className="wiki-cultivation-letter-group" key={group.letter}>
            <div className="wiki-cultivation-letter-heading">
              <h2>{group.letter}</h2>
              <span>{formatNumber(group.rows.length)} characters</span>
            </div>
            <div className="wiki-cultivation-rows">
              {group.rows.map((row) => (
                <button
                  className="wiki-cultivation-row"
                  key={row.character.id}
                  type="button"
                  onClick={() => onSelectCharacterProgression(row.character)}
                >
                  <strong>{row.character.name}</strong>
                  <span className="wiki-realm-tag">{row.realm}</span>
                  <span>{row.stage}</span>
                  <span className="wiki-row-action">›</span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </section>
    </article>
  );
}
