import React from "react";
import {
  Building2,
  Layers3,
  MapPin,
  Package,
  Search,
  Sparkles,
  Users,
} from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { formatCultivationValue, initialsForName } from "../../utils/wikiFormat.js";
import { ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemsIndex.jsx";
import { skillCategoryClass } from "./WikiSkillsIndex.jsx";

const TABS = [
  { id: "all", label: "All", Icon: Layers3 },
  { id: "characters", label: "Characters", Icon: Users },
  { id: "skills", label: "Skills", Icon: Sparkles },
  { id: "items", label: "Items", Icon: Package },
  { id: "organizations", label: "Organizations", Icon: Building2 },
  { id: "places", label: "Places", Icon: MapPin },
];

const PREVIEW_LIMIT = 4;

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
  const index = value.toLowerCase().indexOf(query.trim().toLowerCase());

  if (!query.trim() || index === -1) {
    return value;
  }

  return (
    <>
      {value.slice(0, index)}
      <mark>{value.slice(index, index + query.length)}</mark>
      {value.slice(index + query.length)}
    </>
  );
}

function characterAffiliation(character) {
  return character.faction_or_affiliation || character.origin || character.current_position || "";
}

function skillKnownBy(skill) {
  const names = (skill.characters || [])
    .map((relationship) => relationship.character_name || relationship.character?.name)
    .filter(Boolean);

  if (!names.length) return skill.description || "";

  return `Known by: ${names.slice(0, 2).join(", ")}${names.length > 2 ? " +" : ""}`;
}

function itemUsedBy(item) {
  const names = (item.characters || [])
    .map((relationship) => relationship.character_name || relationship.character?.name)
    .filter(Boolean);

  if (!names.length) return item.description || "";

  return `Used by: ${names.length > 2 ? "Many Characters" : names.join(", ")}`;
}

function SearchResultItem({ query, result, onSelect }) {
  if (result.type === "character") {
    const cultivation = formatCultivationValue(result.record.current_cultivation_level);
    const subtitle = characterAffiliation(result.record);

    return (
      <button className="wiki-global-search-result" type="button" onClick={() => onSelect(result)}>
        <span className={`wiki-character-initials tone-${result.record.id % 6}`}>
          {initialsForName(result.record.name)}
        </span>
        <span>
          <strong><Highlight query={query} text={result.record.name} /></strong>
          <small>{subtitle || "—"}</small>
        </span>
        {cultivation ? <em className="wiki-cultivation-badge">{cultivation}</em> : null}
      </button>
    );
  }

  if (result.type === "skill") {
    return (
      <button className="wiki-global-search-result" type="button" onClick={() => onSelect(result)}>
        <span className="wiki-skill-icon small">S</span>
        <span>
          <strong><Highlight query={query} text={result.record.name} /></strong>
          <small>{skillKnownBy(result.record)}</small>
        </span>
        {result.record.category ? (
          <em className={`wiki-type-badge skill ${skillCategoryClass(result.record.category)}`}>
            {result.record.category}
          </em>
        ) : null}
      </button>
    );
  }

  if (result.type === "item") {
    const type = itemTypeFor(result.record);

    return (
      <button className="wiki-global-search-result" type="button" onClick={() => onSelect(result)}>
        <span className={`wiki-item-type-icon ${type}`}>
          <ItemTypeIcon type={type} />
        </span>
        <span>
          <strong><Highlight query={query} text={result.record.name} /></strong>
          <small>{itemUsedBy(result.record)}</small>
        </span>
        <em className={`wiki-type-badge ${type}`}>{itemTypeLabel(type)}</em>
      </button>
    );
  }

  return null;
}

function SearchSection({ count, label, query, results, onSelect, onViewAll }) {
  return (
    <section className="wiki-global-search-section">
      <div>
        <h3>{label} ({count})</h3>
        {count > results.length ? <button type="button" onClick={onViewAll}>View all</button> : null}
      </div>
      {results.length ? (
        <div className="wiki-global-search-results">
          {results.map((result) => (
            <SearchResultItem key={`${result.type}-${result.record.id}`} query={query} result={result} onSelect={onSelect} />
          ))}
        </div>
      ) : (
        <p>No matching {label.toLowerCase()}.</p>
      )}
    </section>
  );
}

export default function WikiGlobalSearch({
  characters = [],
  items = [],
  novel,
  onSelectCharacter,
  onSelectItem,
  onSelectSkill,
  skills = [],
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const containerRef = React.useRef(null);
  const [activeTab, setActiveTab] = React.useState("all");
  const [isOpen, setIsOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const isSearchPage = location.pathname.endsWith("/search");

  const results = React.useMemo(() => {
    const characterResults = characters
      .filter((character) => {
        const aliasText = (character.aliases || []).map((alias) => alias.alias).join(" ");
        return includesQuery([character.name, aliasText, character.titles], query);
      })
      .map((record) => ({ type: "character", record }));

    const skillResults = skills
      .filter((skill) => {
        const aliasText = (skill.aliases || []).map((alias) => alias.alias).join(" ");
        return includesQuery([skill.name, aliasText, skill.category], query);
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

  React.useEffect(() => {
    function handlePointerDown(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  React.useEffect(() => {
    document.body.classList.toggle("wiki-global-search-open", isOpen);

    return () => {
      document.body.classList.remove("wiki-global-search-open");
    };
  }, [isOpen]);

  React.useEffect(() => {
    if (isSearchPage) {
      setQuery(searchParams.get("q") || "");
    }
  }, [isSearchPage, searchParams]);

  function updateSearchPageQuery(value) {
    if (!isSearchPage) return;

    const nextParams = new URLSearchParams(searchParams);
    const trimmedValue = value.trim();

    if (trimmedValue) {
      nextParams.set("q", value);
    } else {
      nextParams.delete("q");
      nextParams.delete("type");
    }

    setSearchParams(nextParams, { replace: true });
  }

  function viewAllPath(type = activeTab) {
    const encodedQuery = encodeURIComponent(query.trim());

    if (!novel?.id || !encodedQuery) return "/wiki/novels";
    if (type === "characters") return `/wiki/novels/${novel.id}/characters?q=${encodedQuery}`;
    if (type === "skills") return `/wiki/novels/${novel.id}/skills?q=${encodedQuery}`;
    if (type === "items") return `/wiki/novels/${novel.id}/items?q=${encodedQuery}`;

    return `/wiki/novels/${novel.id}/search?q=${encodedQuery}`;
  }

  function handleViewAll(type) {
    navigate(viewAllPath(type));
    setIsOpen(false);
  }

  function handleSelect(result) {
    if (result.type === "character") onSelectCharacter(result.record);
    if (result.type === "skill") onSelectSkill(result.record);
    if (result.type === "item") onSelectItem(result.record);
    setIsOpen(false);
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (query.trim()) {
      handleViewAll("all");
    }
  }

  const visibleTypes = activeTab === "all" ? ["characters", "skills", "items", "organizations", "places"] : [activeTab];

  return (
    <div className={isOpen ? "wiki-global-search open" : "wiki-global-search"} ref={containerRef}>
      <form className="wiki-global-search-form" onSubmit={handleSubmit}>
        <Search aria-hidden="true" size={18} />
        <input
          aria-label="Search this novel"
          className="wiki-search"
          disabled={!novel}
          type="search"
          value={query}
          placeholder="Search this novel..."
          onChange={(event) => {
            const nextQuery = event.target.value;
            setQuery(nextQuery);
            updateSearchPageQuery(nextQuery);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
        />
      </form>

      {isOpen ? (
        <div className="wiki-global-search-overlay">
          <nav className="wiki-global-search-tabs" aria-label="Search result types">
            {TABS.map(({ Icon, id, label }) => (
              <button
                className={activeTab === id ? "active" : ""}
                key={id}
                type="button"
                onClick={() => setActiveTab(id)}
              >
                <Icon aria-hidden="true" size={16} />
                {label}
              </button>
            ))}
          </nav>

          {query.trim() ? (
            <div className={activeTab === "all" ? "wiki-global-search-grid" : "wiki-global-search-grid single"}>
              {visibleTypes.map((type) => {
                const tab = TABS.find((item) => item.id === type);
                const rows = results[type] || [];

                return (
                  <SearchSection
                    count={rows.length}
                    key={type}
                    label={tab?.label || type}
                    query={query}
                    results={rows.slice(0, PREVIEW_LIMIT)}
                    onSelect={handleSelect}
                    onViewAll={() => handleViewAll(type)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="wiki-global-search-empty">
              <Search aria-hidden="true" size={22} />
              <strong>Search this novel</strong>
              <p>Find characters, skills, and items by name or alias.</p>
            </div>
          )}

          {query.trim() ? (
            <button className="wiki-global-search-all" type="button" onClick={() => handleViewAll("all")}>
              View all results for "{query.trim()}" <span aria-hidden="true">→</span>
            </button>
          ) : null}

          <div className="wiki-global-search-footer">
            <span>Press <kbd>Enter</kbd> to view all results</span>
            {query.trim() ? <span>{totalCount} matches in this novel</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
