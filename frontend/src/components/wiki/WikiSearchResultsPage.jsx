import React from "react";
import { Building2, Layers3, MapPin, Package, Search, Sparkles, Users } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import {
  chapterLabel,
  formatCultivationValue,
  formatNumber,
  initialsForName,
  skillCategoryClass,
} from "../../utils/wikiFormat.js";
import { ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemTypes.jsx";

const SEARCH_TABS = [
  { id: "all", label: "All", Icon: Layers3 },
  { id: "characters", label: "Characters", Icon: Users },
  { id: "skills", label: "Skills", Icon: Sparkles },
  { id: "items", label: "Items", Icon: Package },
  { id: "organizations", label: "Organizations", Icon: Building2 },
  { id: "places", label: "Places", Icon: MapPin },
];

const VALID_TYPES = new Set(SEARCH_TABS.map((tab) => tab.id));

function normalized(value) {
  return String(value || "").toLowerCase();
}

function includesQuery(values, query) {
  const q = query.trim().toLowerCase();

  if (!q) return false;

  return values.some((value) => normalized(value).includes(q));
}

function Highlight({ text, query }) {
  const value = String(text || "");
  const trimmedQuery = query.trim();
  const index = value.toLowerCase().indexOf(trimmedQuery.toLowerCase());

  if (!trimmedQuery || index === -1) {
    return value;
  }

  return (
    <>
      {value.slice(0, index)}
      <mark>{value.slice(index, index + trimmedQuery.length)}</mark>
      {value.slice(index + trimmedQuery.length)}
    </>
  );
}

function isUnknown(value) {
  return !value || /^unknown/i.test(String(value).trim());
}

function characterAffiliation(character) {
  const primary = character.faction_or_affiliation || character.origin;
  const parts = [character.current_position, primary]
    .map((value) => String(value || "").trim())
    .filter((value) => value && !isUnknown(value));

  return [...new Set(parts)].join(" · ");
}

function skillChapter(skill) {
  return (
    skill.evidence?.[0]?.chapter
    || (skill.characters || []).find((relationship) => relationship.chapter)?.chapter
    || null
  );
}

function cleanPreview(value, fallback) {
  return (value || fallback).replace(/\s+/g, " ");
}

function SearchResultRow({ query, result, onSelect }) {
  if (result.type === "character") {
    const cultivation = formatCultivationValue(result.record.current_cultivation_level);
    const subtitle = characterAffiliation(result.record) || "—";
    const firstAppearance = result.record.first_appeared_chapter
      ? chapterLabel(result.record.first_appeared_chapter)
      : "Unknown chapter";

    return (
      <button className="wiki-character-row" type="button" onClick={() => onSelect(result)}>
        <span className={`wiki-character-initials tone-${result.record.id % 6}`}>
          {initialsForName(result.record.name)}
        </span>
        <span className="wiki-character-row-main">
          <span>
            <strong><Highlight query={query} text={result.record.name} /></strong>
            {cultivation ? <em className="wiki-cultivation-badge">{cultivation}</em> : null}
          </span>
          <small>{subtitle}</small>
        </span>
        <span className="wiki-character-first-appearance">
          <small>First Appearance:</small>
          <strong>{firstAppearance}</strong>
        </span>
        <span className="wiki-row-action">›</span>
      </button>
    );
  }

  if (result.type === "skill") {
    const firstChapter = skillChapter(result.record);
    const description = cleanPreview(result.record.description, "No description recorded yet.");

    return (
      <button className="wiki-skill-index-row" type="button" onClick={() => onSelect(result)}>
        <span className="wiki-skill-icon small">S</span>
        <span className="wiki-skill-index-main">
          <strong><Highlight query={query} text={result.record.name} /></strong>
          <small className={`wiki-type-badge skill ${skillCategoryClass(result.record.category)}`}>
            {result.record.category || "Skill"}
          </small>
        </span>
        <span className="wiki-skill-index-description">{description}</span>
        <span className="wiki-skill-index-chapter">
          <small>First Appeared</small>
          <strong>{firstChapter ? chapterLabel(firstChapter) : "Unknown"}</strong>
        </span>
        <span className="wiki-row-action">›</span>
      </button>
    );
  }

  if (result.type === "item") {
    const itemType = itemTypeFor(result.record);
    const description = cleanPreview(result.record.description, "No description recorded yet.");

    return (
      <button className="wiki-entity-row item-index-row" type="button" onClick={() => onSelect(result)}>
        <span className={`wiki-item-type-icon ${itemType}`}>
          <ItemTypeIcon type={itemType} />
        </span>
        <strong><Highlight query={query} text={result.record.name} /></strong>
        <span className={`wiki-type-badge ${itemType}`}>{itemTypeLabel(itemType).toUpperCase()}</span>
        <span>{description}</span>
        <span className="wiki-row-action">›</span>
      </button>
    );
  }

  return null;
}

function SearchResultGroup({ label, query, results, onSelect }) {
  return (
    <section className="wiki-search-result-group">
      <header>
        <h2>{label}</h2>
        <span>{formatNumber(results.length)}</span>
      </header>
      {results.length ? (
        <div className="wiki-search-result-list">
          {results.map((result) => (
            <SearchResultRow
              key={`${result.type}-${result.record.id}`}
              query={query}
              result={result}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : (
        <p className="wiki-muted-copy">No matching {label.toLowerCase()}.</p>
      )}
    </section>
  );
}

export default function WikiSearchResultsPage({
  characters = [],
  items = [],
  novel,
  onSelectCharacter,
  onSelectItem,
  onSelectSkill,
  skills = [],
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const requestedType = searchParams.get("type") || "all";
  const activeType = VALID_TYPES.has(requestedType) ? requestedType : "all";

  function updateParams(nextValues) {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(nextValues).forEach(([key, value]) => {
      if (!value || value === "all") {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    setSearchParams(nextParams, { replace: false });
  }

  const results = React.useMemo(() => {
    const characterResults = characters
      .filter((character) => {
        const aliases = (character.aliases || []).map((alias) => alias.alias).join(" ");
        return includesQuery([character.name, aliases, character.titles], query);
      })
      .map((record) => ({ type: "character", record }));

    const skillResults = skills
      .filter((skill) => {
        const aliases = (skill.aliases || []).map((alias) => alias.alias).join(" ");
        return includesQuery([skill.name, aliases, skill.category], query);
      })
      .map((record) => ({ type: "skill", record }));

    const itemResults = items
      .filter((item) => includesQuery([item.name, item.category], query))
      .map((record) => ({ type: "item", record }));

    return {
      characters: characterResults,
      items: itemResults,
      organizations: [],
      places: [],
      skills: skillResults,
    };
  }, [characters, items, query, skills]);

  const totalCount = Object.values(results).reduce((total, rows) => total + rows.length, 0);
  const visibleTypes = activeType === "all"
    ? ["characters", "skills", "items", "organizations", "places"].filter((type) => results[type]?.length)
    : [activeType];

  function handleSelect(result) {
    if (result.type === "character") onSelectCharacter(result.record);
    if (result.type === "skill") onSelectSkill(result.record);
    if (result.type === "item") onSelectItem(result.record);
  }

  return (
    <article className="wiki-search-results-page">
      <header className="wiki-search-results-header">
        <div>
          <h1>Search Results</h1>
          <p>
            {query.trim()
              ? `${formatNumber(totalCount)} results for "${query.trim()}"`
              : `Search across ${novel?.title || "this novel"}`}
          </p>
        </div>
      </header>

      <nav className="wiki-search-results-tabs" aria-label="Search result types">
        {SEARCH_TABS.map(({ Icon, id, label }) => (
          <button
            className={activeType === id ? "active" : ""}
            key={id}
            type="button"
            onClick={() => updateParams({ type: id })}
          >
            <Icon aria-hidden="true" size={16} />
            {label}
            <span>{id === "all" ? formatNumber(totalCount) : formatNumber(results[id]?.length || 0)}</span>
          </button>
        ))}
      </nav>

      {query.trim() && visibleTypes.length ? (
        <div className="wiki-search-result-groups">
          {visibleTypes.map((type) => {
            const tab = SEARCH_TABS.find((item) => item.id === type);
            return (
              <SearchResultGroup
                key={type}
                label={tab?.label || type}
                query={query}
                results={results[type] || []}
                onSelect={handleSelect}
              />
            );
          })}
        </div>
      ) : query.trim() ? (
        <section className="wiki-search-results-empty">
          <Search aria-hidden="true" size={24} />
          <strong>No results found</strong>
          <p>Try a different name, alias, title, skill, or item.</p>
        </section>
      ) : (
        <section className="wiki-search-results-empty">
          <Search aria-hidden="true" size={24} />
          <strong>Start searching this novel</strong>
          <p>Search names, aliases, and titles across characters, skills, and items.</p>
        </section>
      )}
    </article>
  );
}
