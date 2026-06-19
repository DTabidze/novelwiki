import React from "react";
import { Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatNumber } from "../../utils/wikiFormat.js";
import { ITEM_TYPES, ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemTypes.jsx";

const PAGE_SIZE = 20;

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

  function updateFilters(nextValues, options = {}) {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(nextValues).forEach(([key, value]) => {
      if (!value || value === "all" || value === "All" || (key === "page" && Number(value) <= 1)) {
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
          <label className="wiki-local-search-field">
            <Search aria-hidden="true" size={18} />
            <input
              type="search"
              value={search}
              placeholder="Search items..."
              onChange={(event) => updateFilters({ q: event.target.value, page: 1 }, { replace: Boolean(search) })}
            />
          </label>
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
            <button type="button" onClick={() => updateFilters({ q: "", page: 1 }, { replace: true })}>
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
