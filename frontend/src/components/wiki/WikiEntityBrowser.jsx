import React from "react";
import { Search } from "lucide-react";
import { formatNumber } from "../../utils/wikiFormat.js";
import { ITEM_TYPES, ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemTypes.jsx";

export default function WikiEntityBrowser({ entities, iconLabel, onSelectEntity, pageTitle }) {
  const [activeLetter, setActiveLetter] = React.useState("All");
  const [activeType, setActiveType] = React.useState("all");
  const [searchTerm, setSearchTerm] = React.useState("");
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
  const entityLabel = pageTitle.toLowerCase();
  const isItemsPage = pageTitle === "Items";
  const sortedEntities = [...entities].sort((first, second) => first.name.localeCompare(second.name));
  const filteredEntities = sortedEntities.filter((entity) => {
    const firstLetter = (entity.name || "?").trim().slice(0, 1).toUpperCase();
    const type = itemTypeFor(entity);
    const matchesLetter = activeLetter === "All" || firstLetter === activeLetter;
    const matchesType = !isItemsPage || activeType === "all" || type === activeType;
    const matchesSearch = entity.name.toLowerCase().includes(searchTerm.trim().toLowerCase());

    return matchesLetter && matchesType && matchesSearch;
  });
  const groupedEntities = alphabet
    .map((letter) => ({
      letter,
      rows: filteredEntities.filter((entity) => (entity.name || "?").trim().slice(0, 1).toUpperCase() === letter),
    }))
    .filter((group) => group.rows.length > 0);

  return (
    <article className="wiki-index-page wiki-entity-browser">
      <section className="wiki-index-header">
        <div>
          <h1>{pageTitle}</h1>
          <p>
            {formatNumber(entities.length)} {entityLabel}
          </p>
        </div>
        <div className="wiki-index-tools single">
          <label className="wiki-local-search-field">
            <Search aria-hidden="true" size={18} />
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder={`Search ${entityLabel}...`}
            />
          </label>
        </div>
      </section>

      <nav className={isItemsPage ? "wiki-index-alphabet has-secondary-filter" : "wiki-index-alphabet"} aria-label={`Filter ${entityLabel} by first letter`}>
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

      {isItemsPage ? (
        <nav className="wiki-index-filter-row wiki-type-filter-nav" aria-label="Filter items by type">
          {ITEM_TYPES.map((type) => (
            <button
              className={activeType === type.key ? `active ${type.key}` : type.key}
              key={type.key}
              type="button"
              onClick={() => setActiveType(type.key)}
            >
              {type.key === "all" ? <span className="wiki-type-dot" /> : <ItemTypeIcon type={type.key} />}
              {type.label}
            </button>
          ))}
        </nav>
      ) : null}

      <section className="wiki-entity-index">
        {filteredEntities.length === 0 ? <p>No matching {entityLabel} found.</p> : null}
        {groupedEntities.map((group) => (
          <section className="wiki-cultivation-letter-group" key={group.letter}>
            <div className="wiki-cultivation-letter-heading">
              <h2>{group.letter}</h2>
              <span>
                {formatNumber(group.rows.length)} {entityLabel}
              </span>
            </div>
            <div className="wiki-entity-rows">
              {group.rows.map((entity) => {
                const type = itemTypeFor(entity);

                return (
                  <button
                    className={isItemsPage ? "wiki-entity-row item-index-row" : "wiki-entity-row"}
                    key={entity.id}
                    type="button"
                    onClick={() => onSelectEntity(entity)}
                  >
                    {isItemsPage ? (
                      <span className={`wiki-item-type-icon ${type}`}>
                        <ItemTypeIcon type={type} />
                      </span>
                    ) : null}
                    <strong>{entity.name}</strong>
                    <span className={isItemsPage ? `wiki-type-badge ${type}` : ""}>
                      {isItemsPage ? itemTypeLabel(type).toUpperCase() : entity.category || iconLabel}
                    </span>
                    <span>{entity.description || ""}</span>
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
