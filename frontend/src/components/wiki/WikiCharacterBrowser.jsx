import React from "react";
import { Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { chapterLabel, formatCultivationValue, formatNumber } from "../../utils/wikiFormat.js";

const PAGE_SIZE = 20;
const SKELETON_ROWS = Array.from({ length: 4 }, (_, index) => index);
const QUICK_FILTERS = [
  { key: "gender", value: "male", label: "Male" },
  { key: "gender", value: "female", label: "Female" },
  { key: "status", value: "alive", label: "Alive" },
  { key: "status", value: "deceased", label: "Deceased" },
];

function characterMatchesSearch(character, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) return true;

  const aliasText = (character.aliases || []).map((alias) => alias.alias).join(" ");
  return [character.name, aliasText].some((value) =>
    String(value || "").toLowerCase().includes(normalizedQuery)
  );
}

function characterInitials(name) {
  const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return String(parts[0] || "?").slice(0, 2).toUpperCase();
}

function isUnknown(value) {
  return !value || /^unknown/i.test(String(value).trim());
}

function normalizedStatus(value) {
  const normalized = String(value || "").trim().toLowerCase();

  if (["dead", "deceased", "died"].includes(normalized)) {
    return "deceased";
  }

  return normalized;
}

function statusFilterLabel(value) {
  if (normalizedStatus(value) === "deceased") {
    return "Deceased";
  }

  if (normalizedStatus(value) === "alive") {
    return "Alive";
  }

  return value;
}

function characterAffiliation(character) {
  const primary = character.faction_or_affiliation || character.origin;
  const parts = [character.current_position, primary]
    .map((value) => String(value || "").trim())
    .filter((value) => value && !isUnknown(value));

  return [...new Set(parts)].join(" · ");
}

function pageWindow(currentPage, totalPages) {
  const pages = [];
  const start = Math.max(1, Math.min(currentPage - 1, totalPages - 2));
  const end = Math.min(totalPages, start + 2);

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  return pages;
}

function CharacterSkeletonRows({ view }) {
  return SKELETON_ROWS.map((index) => (
    <div
      aria-hidden="true"
      className={view === "grid" ? "wiki-character-row wiki-character-skeleton-card" : "wiki-character-row wiki-character-skeleton-row"}
      key={index}
    >
      <span className="wiki-skeleton wiki-character-skeleton-avatar" />
      <span className="wiki-character-row-main">
        <span>
          <span className="wiki-skeleton wiki-skeleton-title" />
          <span className="wiki-skeleton wiki-skeleton-badge" />
        </span>
        <span className="wiki-skeleton wiki-skeleton-subtitle" />
      </span>
      <span className="wiki-character-first-appearance">
        <span className="wiki-skeleton wiki-skeleton-meta-short" />
        <span className="wiki-skeleton wiki-skeleton-meta-long" />
      </span>
    </div>
  ));
}

export default function WikiCharacterBrowser({ characters, isLoading = false, novel, onSelectCharacter }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("q") || "";
  const letter = searchParams.get("letter") || "All";
  const gender = searchParams.get("gender") || "all";
  const status = searchParams.get("status") || "all";
  const sort = searchParams.get("sort") || "name_asc";
  const view = searchParams.get("view") || "list";
  const bookmarked = searchParams.get("bookmarked") === "1";
  const requestedPage = Math.max(1, Number(searchParams.get("page")) || 1);
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

  function updateFilters(nextValues, options = {}) {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(nextValues).forEach(([key, value]) => {
      if (!value || value === "All" || value === "all" || (key === "page" && Number(value) <= 1)) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    setSearchParams(nextParams, { replace: Boolean(options.replace) });
  }

  function clearAllFilters() {
    setSearchParams(new URLSearchParams(), { replace: false });
  }

  const filteredCharacters = React.useMemo(() => {
    if (isLoading) {
      return [];
    }

    const rows = characters
      .filter((character) => characterMatchesSearch(character, search))
      .filter((character) => gender === "all" || String(character.gender || "").toLowerCase() === gender)
      .filter((character) => status === "all" || normalizedStatus(character.status) === normalizedStatus(status))
      .filter((character) => !bookmarked || character.is_bookmarked)
      .filter((character) => {
        const firstLetter = (character.name || "?").trim().slice(0, 1).toUpperCase();
        return letter === "All" || firstLetter === letter;
      });

    return rows.sort((first, second) => {
      if (sort === "name_desc") {
        return second.name.localeCompare(first.name);
      }

      return first.name.localeCompare(second.name);
    });
  }, [bookmarked, characters, gender, isLoading, letter, search, sort, status]);

  const totalPages = Math.max(1, Math.ceil(filteredCharacters.length / PAGE_SIZE));
  const currentPage = Math.min(requestedPage, totalPages);
  const startIndex = filteredCharacters.length ? (currentPage - 1) * PAGE_SIZE : 0;
  const visibleCharacters = filteredCharacters.slice(startIndex, startIndex + PAGE_SIZE);
  const endIndex = Math.min(startIndex + visibleCharacters.length, filteredCharacters.length);
  const hasActiveFilters = Boolean(search || letter !== "All" || gender !== "all" || status !== "all" || bookmarked);

  React.useEffect(() => {
    if (isLoading) {
      return;
    }

    if (requestedPage !== currentPage) {
      updateFilters({ page: currentPage });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, isLoading, requestedPage]);

  return (
    <article className="wiki-index-page wiki-character-browser">
      <header className="wiki-index-header">
        <div>
          <h1>Characters</h1>
        </div>
        <div className="wiki-index-tools single">
          <label className="wiki-local-search-field">
            <Search aria-hidden="true" size={18} />
            <input
              type="search"
              value={search}
              onChange={(event) => updateFilters({ q: event.target.value, page: 1 }, { replace: Boolean(search) })}
              placeholder="Search characters..."
            />
          </label>
        </div>
      </header>

      {hasActiveFilters ? (
        <section className="wiki-active-filter-bar" aria-label="Active filters">
          <strong>Active Filters:</strong>
          {search ? (
            <button type="button" onClick={() => updateFilters({ q: "", page: 1 }, { replace: true })}>
              Search: {search} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {letter !== "All" ? (
            <button type="button" onClick={() => updateFilters({ letter: "All", page: 1 })}>
              Letter: {letter} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {gender !== "all" ? (
            <button type="button" onClick={() => updateFilters({ gender: "all", page: 1 })}>
              Gender: {gender} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {status !== "all" ? (
            <button type="button" onClick={() => updateFilters({ status: "all", page: 1 })}>
              Status: {statusFilterLabel(status)} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {bookmarked ? (
            <button type="button" onClick={() => updateFilters({ bookmarked: "", page: 1 })}>
              Bookmarked <span aria-hidden="true">x</span>
            </button>
          ) : null}
          <button className="clear" type="button" onClick={clearAllFilters}>Clear all</button>
        </section>
      ) : null}

      <nav className="wiki-index-alphabet has-secondary-filter" aria-label="Filter characters by first letter">
        <button
          className={letter === "All" ? "active" : ""}
          type="button"
          onClick={() => updateFilters({ letter: "All", page: 1 })}
        >
          All
        </button>
        {alphabet.map((alphabetLetter) => (
          <button
            className={letter === alphabetLetter ? "active" : ""}
            key={alphabetLetter}
            type="button"
            onClick={() => updateFilters({ letter: alphabetLetter, page: 1 })}
          >
            {alphabetLetter}
          </button>
        ))}
      </nav>

      <nav className="wiki-index-filter-row wiki-character-quick-filters" aria-label="Quick character filters">
        <button
          className={gender === "all" ? "active" : ""}
          type="button"
          onClick={() => updateFilters({ gender: "all", page: 1 })}
        >
          All Genders
        </button>
        {QUICK_FILTERS.map((filter) => {
          const active = searchParams.get(filter.key) === filter.value;

          return (
            <button
              className={active ? `active ${filter.value}` : filter.value}
              key={`${filter.key}-${filter.value}`}
              type="button"
              onClick={() => updateFilters({ [filter.key]: active ? "all" : filter.value, page: 1 })}
            >
              {filter.label}
            </button>
          );
        })}
      </nav>

      <section className="wiki-index-toolbar">
        <strong>
          {isLoading ? (
            <span className="wiki-inline-loading">
              <span aria-hidden="true" />
              Loading characters...
            </span>
          ) : (
            `${formatNumber(filteredCharacters.length)} characters found`
          )}
        </strong>
        <div>
          <label>
            <span>Sort by:</span>
            <select value={sort} onChange={(event) => updateFilters({ sort: event.target.value, page: 1 })}>
              <option value="name_asc">Name (A-Z)</option>
              <option value="name_desc">Name (Z-A)</option>
            </select>
          </label>
          <button
            className={bookmarked ? "wiki-bookmarked-filter active" : "wiki-bookmarked-filter"}
            type="button"
            onClick={() => updateFilters({ bookmarked: bookmarked ? "" : "1", page: 1 })}
          >
            Bookmarked
          </button>
          <div className="wiki-view-toggle" aria-label="View mode">
            <button className={view === "list" ? "active" : ""} type="button" onClick={() => updateFilters({ view: "list" })}>☰</button>
            <button className={view === "grid" ? "active" : ""} type="button" onClick={() => updateFilters({ view: "grid" })}>▦</button>
          </div>
        </div>
      </section>

      <section className="wiki-character-index">
        <div className={view === "grid" ? "wiki-character-rows grid" : "wiki-character-rows"}>
          {isLoading ? <CharacterSkeletonRows view={view} /> : null}
          {!isLoading && visibleCharacters.length ? visibleCharacters.map((character) => {
            const cultivation = character.current_cultivation_level
              ? formatCultivationValue(character.current_cultivation_level)
              : "";
            const affiliation = characterAffiliation(character);
            const firstAppearance = character.first_appeared_chapter
              ? chapterLabel(character.first_appeared_chapter)
              : "Unknown chapter";

            return (
              <button
                className="wiki-character-row"
                key={character.id}
                type="button"
                onClick={() => onSelectCharacter(character)}
              >
                <span className={`wiki-character-initials tone-${character.id % 6}`}>
                  {characterInitials(character.name)}
                </span>
                <span className="wiki-character-row-main">
                  <span>
                    <strong>{character.name}</strong>
                    {cultivation ? <em className="wiki-cultivation-badge">{cultivation}</em> : null}
                  </span>
                  <small>{affiliation || "—"}</small>
                </span>
                <span className="wiki-character-first-appearance">
                  <small>First Appearance:</small>
                  <strong>{firstAppearance}</strong>
                </span>
                <span className="wiki-row-action">›</span>
              </button>
            );
          }) : null}
          {!isLoading && !visibleCharacters.length ? (
            <p className="wiki-muted-copy">No matching characters found.</p>
          ) : null}
        </div>
      </section>

      {!isLoading ? (
        <footer className="wiki-index-pagination">
          <div>
            {pageWindow(currentPage, totalPages).map((page) => (
              <button
                className={page === currentPage ? "active" : ""}
                key={page}
                type="button"
                onClick={() => updateFilters({ page })}
              >
                {page}
              </button>
            ))}
            {currentPage < totalPages ? (
              <button type="button" onClick={() => updateFilters({ page: currentPage + 1 })}>›</button>
            ) : null}
          </div>
          <span>
            Showing {filteredCharacters.length ? startIndex + 1 : 0} to {endIndex} of {formatNumber(filteredCharacters.length)} characters
          </span>
        </footer>
      ) : null}
    </article>
  );
}
