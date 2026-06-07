import React from "react";
import { useSearchParams } from "react-router-dom";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatNumber } from "../../utils/wikiFormat.js";

const ITEM_TYPES = [
  { key: "all", label: "All Types" },
  { key: "weapon", label: "Weapons" },
  { key: "artifact", label: "Artifacts" },
  { key: "pill", label: "Pills" },
  { key: "manual", label: "Manuals" },
  { key: "material", label: "Materials" },
  { key: "miscellaneous", label: "Miscellaneous" },
];

const PAGE_SIZE = 20;

export function itemTypeFor(item) {
  const searchable = `${item.category || ""} ${item.name || ""}`.toLowerCase();

  if (/(weapon|sword|blade|spear|bow|dagger)/.test(searchable)) {
    return "weapon";
  }

  if (/(artifact|treasure|mirror|gourd|pendant|bag of holding)/.test(searchable)) {
    return "artifact";
  }

  if (/(pill|medicine|elixir|pellet)/.test(searchable)) {
    return "pill";
  }

  if (/(manual|book|scroll|jade slip|slip)/.test(searchable)) {
    return "manual";
  }

  if (/(material|essence|core|stone|crystal|ore)/.test(searchable)) {
    return "material";
  }

  return "miscellaneous";
}

export function itemTypeLabel(type) {
  return ITEM_TYPES.find((itemType) => itemType.key === type)?.label.replace(/s$/, "") || "Miscellaneous";
}

export function ItemTypeIcon({ type }) {
  const iconProps = {
    "aria-hidden": "true",
    fill: "none",
    height: "20",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: "2",
    viewBox: "0 0 24 24",
    width: "20",
  };
  const paths = {
    weapon: (
      <>
        <polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5" />
        <line x1="13" x2="19" y1="19" y2="13" />
        <line x1="16" x2="20" y1="16" y2="20" />
        <line x1="19" x2="21" y1="21" y2="19" />
      </>
    ),
    artifact: (
      <>
        <path d="M6 3h12l4 6-10 13L2 9Z" />
        <path d="M11 3 8 9l4 13 4-13-3-6" />
        <path d="M2 9h20" />
      </>
    ),
    pill: (
      <>
        <path d="M10 2v7.31" />
        <path d="M14 9.3V2" />
        <path d="M8.5 2h7" />
        <path d="M14 9.3a6.5 6.5 0 1 1-4 0" />
        <path d="M5.52 16h12.96" />
      </>
    ),
    manual: (
      <>
        <path d="M15 12h-5" />
        <path d="M15 8h-5" />
        <path d="M19 17V5a2 2 0 0 0-2-2H4" />
        <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
      </>
    ),
    material: (
      <>
        <path d="M8.5 14.5A4 4 0 0 0 12 21a6 6 0 0 0 6-6c0-4-3-6-3-10-2 2-7 4-6.5 9.5Z" />
        <path d="M12 21c0-3 1.5-5 4-7" />
      </>
    ),
    miscellaneous: (
      <>
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
        <path d="M3.3 7 12 12l8.7-5" />
        <path d="M12 22V12" />
      </>
    ),
  };

  return <svg {...iconProps}>{paths[type] || paths.miscellaneous}</svg>;
}

function itemMatchesCharacter(item, characterId) {
  if (!characterId) return true;
  return (item.characters || []).some((relationship) => relationship.character_id === characterId);
}

function itemMatchesSearch(item, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) return true;

  return String(item.name || "").toLowerCase().includes(normalizedQuery);
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

export default function WikiItemsIndex({ characters, items, novel, onSelectCharacter, onSelectItem }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const characterId = Number(searchParams.get("character_id")) || null;
  const search = searchParams.get("q") || "";
  const type = searchParams.get("type") || "all";
  const letter = searchParams.get("letter") || "All";
  const requestedPage = Math.max(1, Number(searchParams.get("page")) || 1);
  const selectedCharacter = characterId
    ? characters.find((character) => character.id === characterId)
    : null;
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

  function updateFilters(nextValues) {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(nextValues).forEach(([key, value]) => {
      if (!value || value === "all" || value === "All" || (key === "page" && Number(value) <= 1)) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    setSearchParams(nextParams, { replace: false });
  }

  function clearAllFilters() {
    setSearchParams(new URLSearchParams(), { replace: false });
  }

  function removeCharacterFilter() {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("character_id");
    nextParams.delete("page");
    setSearchParams(nextParams, { replace: false });
  }

  const filteredItems = React.useMemo(() => {
    const rows = items
      .filter((item) => itemMatchesCharacter(item, characterId))
      .filter((item) => itemMatchesSearch(item, search))
      .filter((item) => type === "all" || itemTypeFor(item) === type)
      .filter((item) => {
        const firstLetter = (item.name || "?").trim().slice(0, 1).toUpperCase();
        return letter === "All" || firstLetter === letter;
      });

    return rows.sort((first, second) => first.name.localeCompare(second.name));
  }, [characterId, items, letter, search, type]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const currentPage = Math.min(requestedPage, totalPages);
  const startIndex = filteredItems.length ? (currentPage - 1) * PAGE_SIZE : 0;
  const visibleItems = filteredItems.slice(startIndex, startIndex + PAGE_SIZE);
  const endIndex = Math.min(startIndex + visibleItems.length, filteredItems.length);
  const hasActiveFilters = Boolean(characterId || search || type !== "all" || letter !== "All");

  React.useEffect(() => {
    if (requestedPage !== currentPage) {
      updateFilters({ page: currentPage });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, requestedPage]);

  return (
    <article className="wiki-items-index">
      <header className="wiki-cultivation-header">
        <div>
          <h1>Items</h1>
          <p>{formatNumber(filteredItems.length)} items</p>
        </div>
        <div className="wiki-cultivation-tools single">
          <input
            type="search"
            value={search}
            placeholder="Search items..."
            onChange={(event) => updateFilters({ q: event.target.value, page: 1 })}
          />
        </div>
      </header>

      {hasActiveFilters ? (
        <section className="wiki-active-filter-bar" aria-label="Active filters">
          <strong>Active Filters:</strong>
          {selectedCharacter ? (
            <button type="button" onClick={removeCharacterFilter}>
              Character: {selectedCharacter.name} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {search ? (
            <button type="button" onClick={() => updateFilters({ q: "", page: 1 })}>
              Search: {search} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {type !== "all" ? (
            <button type="button" onClick={() => updateFilters({ type: "all", page: 1 })}>
              Type: {itemTypeLabel(type)} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {letter !== "All" ? (
            <button type="button" onClick={() => updateFilters({ letter: "All", page: 1 })}>
              Letter: {letter} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          <button className="clear" type="button" onClick={clearAllFilters}>Clear all</button>
        </section>
      ) : null}

      {selectedCharacter ? (
        <section className="wiki-character-filter-card">
          <div>
            <WikiAvatar name={selectedCharacter.name} size="small" />
            <div>
              <span>Showing items for:</span>
              <div className="wiki-character-filter-title">
                <strong>{selectedCharacter.name}</strong>
                <button type="button" onClick={() => onSelectCharacter(selectedCharacter)}>
                  View character <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </div>
          <button type="button" onClick={removeCharacterFilter}>Remove filter</button>
        </section>
      ) : null}

      <nav className="wiki-skill-alphabet" aria-label="Filter items by first letter">
        <button className={letter === "All" ? "active" : ""} type="button" onClick={() => updateFilters({ letter: "All", page: 1 })}>
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

      <nav className="wiki-type-filter-nav" aria-label="Filter items by type">
        {ITEM_TYPES.map((itemType) => (
          <button
            className={type === itemType.key ? `active ${itemType.key}` : itemType.key}
            key={itemType.key}
            type="button"
            onClick={() => updateFilters({ type: itemType.key, page: 1 })}
          >
            {itemType.key === "all" ? <span className="wiki-type-dot" /> : <ItemTypeIcon type={itemType.key} />}
            {itemType.label}
          </button>
        ))}
      </nav>

      <section className="wiki-skill-list-toolbar">
        <strong>{formatNumber(filteredItems.length)} items found</strong>
      </section>

      <section className="wiki-entity-index">
        <div className="wiki-entity-rows">
          {visibleItems.length ? visibleItems.map((item) => {
            const itemType = itemTypeFor(item);
            const description = (item.description || "No description recorded yet.").replace(/\s+/g, " ");

            return (
              <button
                className="wiki-entity-row item-index-row"
                key={item.id}
                type="button"
                onClick={() => onSelectItem(item)}
              >
                <span className={`wiki-item-type-icon ${itemType}`}>
                  <ItemTypeIcon type={itemType} />
                </span>
                <strong>{item.name}</strong>
                <span className={`wiki-type-badge ${itemType}`}>{itemTypeLabel(itemType).toUpperCase()}</span>
                <span>{description}</span>
                <span className="wiki-row-action">›</span>
              </button>
            );
          }) : (
            <p className="wiki-muted-copy">No matching items found.</p>
          )}
        </div>
      </section>

      <footer className="wiki-skill-pagination">
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
          Showing {filteredItems.length ? startIndex + 1 : 0} to {endIndex} of {formatNumber(filteredItems.length)} items
        </span>
      </footer>
    </article>
  );
}
