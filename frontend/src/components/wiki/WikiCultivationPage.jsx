import React from "react";
import { Info, Search } from "lucide-react";
import {
  cleanChapterTitle,
  formatCultivationValue,
  formatNumber,
  initialsForName,
} from "../../utils/wikiFormat.js";

const PAGE_SIZE = 20;

function pageWindow(currentPage, totalPages) {
  const pages = [];
  const start = Math.max(1, Math.min(currentPage - 1, totalPages - 2));
  const end = Math.min(totalPages, start + 2);

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  return pages;
}

export default function WikiCultivationPage({
  characters,
  novel,
  onSelectCharacterProgression,
  progressionEvents,
}) {
  const [activeLetter, setActiveLetter] = React.useState("All");
  const [currentPage, setCurrentPage] = React.useState(1);
  const [realmFilter, setRealmFilter] = React.useState("All");
  const [searchTerm, setSearchTerm] = React.useState("");
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

  function latestCultivationEventFor(character) {
    return progressionEvents
      .filter((event) => event.character_id === character.id && event.progression_type === "cultivation_level")
      .filter((event) => event.new_value)
      .sort((first, second) => {
        const firstChapter = first.chapter?.chapter_number || 0;
        const secondChapter = second.chapter?.chapter_number || 0;

        if (firstChapter !== secondChapter) {
          return secondChapter - firstChapter;
        }

        return (second.id || 0) - (first.id || 0);
      })[0];
  }

  function characterMatchesSearch(character) {
    const query = searchTerm.trim().toLowerCase();

    if (!query) return true;

    const aliasText = (character.aliases || []).map((alias) => alias.alias).join(" ");

    return [character.name, aliasText].some((value) =>
      String(value || "").toLowerCase().includes(query)
    );
  }

  const characterRows = characters
    .map((character) => {
      const cultivationEvents = progressionEvents.filter(
        (event) =>
          event.character_id === character.id &&
          event.progression_type === "cultivation_level" &&
          event.new_value
      );
      const latestEvent = latestCultivationEventFor(character);
      const cultivationValue = formatCultivationValue(latestEvent?.new_value || character.current_cultivation_level);

      return {
        character,
        breakthroughCount: cultivationEvents.length,
        chapter: latestEvent?.chapter || null,
        cultivationValue,
        firstLetter: (character.name || "?").trim().slice(0, 1).toUpperCase(),
        realmKey: cultivationValue.toLowerCase(),
      };
    })
    .filter((row) => row.cultivationValue)
    .sort((first, second) => first.character.name.localeCompare(second.character.name));

  const realmOptions = [...new Set(characterRows.map((row) => row.cultivationValue))].sort((first, second) =>
    first.localeCompare(second)
  );
  const filteredRows = characterRows.filter((row) => {
    const matchesLetter = activeLetter === "All" || row.firstLetter === activeLetter;
    const matchesRealm = realmFilter === "All" || row.realmKey === realmFilter;
    const matchesSearch = characterMatchesSearch(row.character);

    return matchesLetter && matchesRealm && matchesSearch;
  });
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = filteredRows.length ? (safeCurrentPage - 1) * PAGE_SIZE : 0;
  const visibleRows = filteredRows.slice(startIndex, startIndex + PAGE_SIZE);
  const endIndex = Math.min(startIndex + visibleRows.length, filteredRows.length);

  React.useEffect(() => {
    setCurrentPage(1);
  }, [activeLetter, realmFilter, searchTerm]);

  React.useEffect(() => {
    if (safeCurrentPage !== currentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  return (
    <article className="wiki-index-page wiki-cultivation-page">
      <section className="wiki-index-header">
        <div>
          <h1>
            Cultivation
            <span
              aria-label="Current cultivation status of characters and their latest known realm."
              className="wiki-index-title-info"
              role="img"
              title="Current cultivation status of characters and their latest known realm."
            >
              <Info aria-hidden="true" size={17} strokeWidth={2.2} />
            </span>
          </h1>
        </div>
        <div className="wiki-index-tools">
          <label className="wiki-local-search-field">
            <Search aria-hidden="true" size={18} />
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search characters..."
            />
          </label>
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

      <nav className="wiki-index-alphabet" aria-label="Filter cultivation characters by first letter">
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

      <section className="wiki-index-toolbar">
        <strong>{formatNumber(filteredRows.length)} characters found</strong>
      </section>

      <section className="wiki-cultivation-index">
        <div className="wiki-cultivation-rows">
          {visibleRows.length ? visibleRows.map((row) => {
            const chapterTitle = cleanChapterTitle(row.chapter);

            return (
              <button
                className="wiki-cultivation-row"
                key={row.character.id}
                type="button"
                onClick={() => onSelectCharacterProgression(row.character)}
              >
                <span className={`wiki-character-initials tone-${row.character.id % 6}`}>
                  {initialsForName(row.character.name)}
                </span>
                <strong>{row.character.name}</strong>
                <span className="wiki-realm-tag">{row.cultivationValue}</span>
                <span className="wiki-cultivation-confirmed" title="Last confirmed chapter">
                  <strong>{row.chapter ? `Chapter ${row.chapter.chapter_number}` : "Unknown chapter"}</strong>
                  {chapterTitle ? <small>{chapterTitle}</small> : null}
                </span>
                <span className="wiki-breakthrough-count">
                  <strong>{formatNumber(row.breakthroughCount)}</strong>
                  <small>{row.breakthroughCount === 1 ? "breakthrough" : "breakthroughs"}</small>
                </span>
                <span className="wiki-row-action">›</span>
              </button>
            );
          }) : (
            <p className="wiki-muted-copy">No matching characters found.</p>
          )}
        </div>
      </section>

      <footer className="wiki-index-pagination">
        <div>
          {pageWindow(safeCurrentPage, totalPages).map((page) => (
            <button
              className={page === safeCurrentPage ? "active" : ""}
              key={page}
              type="button"
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </button>
          ))}
          {safeCurrentPage < totalPages ? (
            <button type="button" onClick={() => setCurrentPage(safeCurrentPage + 1)}>›</button>
          ) : null}
        </div>
        <span>
          Showing {filteredRows.length ? startIndex + 1 : 0} to {endIndex} of {formatNumber(filteredRows.length)} characters
        </span>
      </footer>
    </article>
  );
}
