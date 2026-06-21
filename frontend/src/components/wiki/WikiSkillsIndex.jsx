import React from "react";
import { Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import WikiAvatar from "./WikiAvatar.jsx";
import { chapterLabel, formatNumber, skillCategoryClass } from "../../utils/wikiFormat.js";

const SKILL_CATEGORIES = [
  "Technique",
  "Cultivation Method",
  "Divine Ability",
  "Spell",
  "Martial Art",
  "Combat Move",
  "Movement Skill",
  "Body Refinement",
  "Soul Skill",
  "Alchemy",
  "Formation",
  "Utility",
  "Other",
];

const PAGE_SIZE = 20;

function skillChapter(skill, characterId) {
  const characterRelationship = characterId
    ? (skill.characters || []).find((relationship) => relationship.character_id === characterId)
    : null;

  return (
    characterRelationship?.chapter
    || skill.evidence?.[0]?.chapter
    || (skill.characters || []).find((relationship) => relationship.chapter)?.chapter
    || null
  );
}

function skillMatchesCharacter(skill, characterId) {
  if (!characterId) return true;
  return (skill.characters || []).some((relationship) => relationship.character_id === characterId);
}

function skillMatchesSearch(skill, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) return true;

  const aliasText = (skill.aliases || []).map((alias) => alias.alias).join(" ");
  return [skill.name, aliasText].some((value) =>
    String(value || "").toLowerCase().includes(normalizedQuery)
  );
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

export default function WikiSkillsIndex({ characters, novel, onSelectCharacter, onSelectSkill, skills }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const characterId = Number(searchParams.get("character_id")) || null;
  const search = searchParams.get("q") || "";
  const category = searchParams.get("category") || "all";
  const letter = searchParams.get("letter") || "All";
  const sort = searchParams.get("sort") || "name_asc";
  const view = searchParams.get("view") || "list";
  const bookmarked = searchParams.get("bookmarked") === "1";
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

  const filteredSkills = React.useMemo(() => {
    const rows = skills
      .filter((skill) => skillMatchesCharacter(skill, characterId))
      .filter((skill) => skillMatchesSearch(skill, search))
      .filter((skill) => !bookmarked || skill.is_bookmarked)
      .filter((skill) => category === "all" || String(skill.category || "").toLowerCase() === category.toLowerCase())
      .filter((skill) => {
        const firstLetter = (skill.name || "?").trim().slice(0, 1).toUpperCase();
        return letter === "All" || firstLetter === letter;
      });

    return rows.sort((first, second) => {
      if (sort === "name_desc") {
        return second.name.localeCompare(first.name);
      }

      return first.name.localeCompare(second.name);
    });
  }, [bookmarked, category, characterId, letter, search, skills, sort]);

  const totalPages = Math.max(1, Math.ceil(filteredSkills.length / PAGE_SIZE));
  const currentPage = Math.min(requestedPage, totalPages);
  const startIndex = filteredSkills.length ? (currentPage - 1) * PAGE_SIZE : 0;
  const visibleSkills = filteredSkills.slice(startIndex, startIndex + PAGE_SIZE);
  const endIndex = Math.min(startIndex + visibleSkills.length, filteredSkills.length);
  const hasActiveFilters = Boolean(characterId || search || category !== "all" || letter !== "All" || bookmarked);

  React.useEffect(() => {
    if (requestedPage !== currentPage) {
      updateFilters({ page: currentPage });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, requestedPage]);

  return (
    <article className="wiki-skills-index">
      <header className="wiki-cultivation-header">
        <div>
          <h1>Skills</h1>
          <p>{formatNumber(filteredSkills.length)} skills</p>
        </div>
        <div className="wiki-cultivation-tools">
          <label className="wiki-local-search-field">
            <Search aria-hidden="true" size={18} />
            <input
              type="search"
              value={search}
              placeholder="Search skills..."
              onChange={(event) => updateFilters({ q: event.target.value, page: 1 }, { replace: Boolean(search) })}
            />
          </label>
          <select
            aria-label="Skill category"
            value={category}
            onChange={(event) => updateFilters({ category: event.target.value, page: 1 })}
          >
            <option value="all">All Categories</option>
            {SKILL_CATEGORIES.map((skillCategory) => (
              <option key={skillCategory} value={skillCategory}>{skillCategory}</option>
            ))}
          </select>
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
          {category !== "all" ? (
            <button type="button" onClick={() => updateFilters({ category: "all", page: 1 })}>
              Category: {category} <span aria-hidden="true">x</span>
            </button>
          ) : null}
          {letter !== "All" ? (
            <button type="button" onClick={() => updateFilters({ letter: "All", page: 1 })}>
              Letter: {letter} <span aria-hidden="true">x</span>
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

      {selectedCharacter ? (
        <section className="wiki-character-filter-card">
          <div>
            <WikiAvatar name={selectedCharacter.name} size="small" />
            <div>
              <span>Showing skills for:</span>
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

      <nav className="wiki-skill-alphabet" aria-label="Filter skills by first letter">
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

      <section className="wiki-skill-list-toolbar">
        <strong>{formatNumber(filteredSkills.length)} skills found</strong>
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

      <section className={view === "grid" ? "wiki-skill-results grid" : "wiki-skill-results"}>
        {visibleSkills.length ? visibleSkills.map((skill) => {
          const firstChapter = skillChapter(skill, characterId);
          const description = (skill.description || "No description recorded yet.").replace(/\s+/g, " ");

          return (
            <button className="wiki-skill-index-row" key={skill.id} type="button" onClick={() => onSelectSkill(skill)}>
              <span className="wiki-skill-icon small">S</span>
              <span className="wiki-skill-index-main">
                <strong>{skill.name}</strong>
                <small className={`wiki-type-badge skill ${skillCategoryClass(skill.category)}`}>
                  {skill.category || "Skill"}
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
        }) : (
          <p className="wiki-muted-copy">No matching skills found.</p>
        )}
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
          Showing {filteredSkills.length ? startIndex + 1 : 0} to {endIndex} of {formatNumber(filteredSkills.length)} skills
        </span>
      </footer>
    </article>
  );
}
