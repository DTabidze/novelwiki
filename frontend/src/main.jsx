import React from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import "./styles.css";

const API_BASE_URL = "http://127.0.0.1:5050/api";

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }

  return body.data;
}

function ReviewRecord({ entityType, record, fields, mergeTargets = [], onMerged, onSaved }) {
  const [formValues, setFormValues] = React.useState(() => {
    const values = {};

    fields.forEach((field) => {
      values[field] = record[field] || "";
    });

    values.admin_notes = record.admin_notes || "";
    return values;
  });
  const [isSaving, setIsSaving] = React.useState(false);
  const [mergeTargetId, setMergeTargetId] = React.useState("");

  async function saveRecord(extraValues = {}) {
    setIsSaving(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/review/${entityType}/${record.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...formValues,
          ...extraValues,
        }),
      });

      onSaved(data);
    } finally {
      setIsSaving(false);
    }
  }

  async function mergeCharacter() {
    if (!mergeTargetId) {
      return;
    }

    setIsSaving(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/review/characters/${record.id}/merge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_character_id: Number(mergeTargetId),
        }),
      });

      onMerged(record.id, data);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <article className="mini-record review-record">
      <div className="record-title-row">
        <strong>
          {record.name ||
            record.title ||
            record.new_value ||
            record.character_name ||
            record.entity_type ||
            entityType}
        </strong>
        <span className={`status-pill ${record.review_status}`}>{record.review_status}</span>
      </div>

      {record.character_name && entityType !== "characters" ? (
        <p className="source-line">Character: {record.character_name}</p>
      ) : null}

      {record.skill_name ? <p className="source-line">Skill: {record.skill_name}</p> : null}
      {record.item_name ? <p className="source-line">Item: {record.item_name}</p> : null}

      {record.source_chapter ? (
        <p className="source-line">
          Source: Chapter {record.source_chapter.chapter_number}, {record.source_chapter.title}
        </p>
      ) : null}

      {entityType === "characters" ? (
        <div className="meta-lines">
          <span>
            First mentioned:{" "}
            {record.first_mentioned_chapter
              ? `Chapter ${record.first_mentioned_chapter.chapter_number}`
              : "Unknown"}
          </span>
          <span>
            First appeared:{" "}
            {record.first_appeared_chapter
              ? `Chapter ${record.first_appeared_chapter.chapter_number}`
              : "Unknown"}
          </span>
          {record.current_cultivation_level ? (
            <span>Current cultivation: {record.current_cultivation_level}</span>
          ) : null}
          {record.current_position ? <span>Current position: {record.current_position}</span> : null}
          {record.current_class_rank ? (
            <span>Current class rank: {record.current_class_rank}</span>
          ) : null}
          {record.current_power_rank ? <span>Current power rank: {record.current_power_rank}</span> : null}
        </div>
      ) : null}

      {(entityType === "characters" || entityType === "skills") &&
      record.aliases &&
      record.aliases.length > 0 ? (
        <div className="alias-list">
          <strong>Aliases</strong>
          {record.aliases.map((alias) => (
            <span key={alias.id}>{alias.alias}</span>
          ))}
        </div>
      ) : null}

      {fields.map((field) => (
        <label key={field}>
          {field.replace("_", " ")}
          {field === "description" ? (
            <textarea
              value={formValues[field]}
              onChange={(event) => setFormValues({ ...formValues, [field]: event.target.value })}
            />
          ) : (
            <input
              type="text"
              value={formValues[field]}
              onChange={(event) => setFormValues({ ...formValues, [field]: event.target.value })}
            />
          )}
        </label>
      ))}

      <label>
        admin notes
        <textarea
          value={formValues.admin_notes}
          onChange={(event) => setFormValues({ ...formValues, admin_notes: event.target.value })}
          placeholder="Optional review notes"
        />
      </label>

      {record.evidence && record.evidence.length > 0 ? (
        <div className="evidence-list">
          <strong>Evidence</strong>
          {record.evidence.map((evidence) => (
            <p key={evidence.id}>{evidence.evidence_text}</p>
          ))}
        </div>
      ) : null}

      <div className="review-actions">
        <button type="button" disabled={isSaving} onClick={() => saveRecord()}>
          Save
        </button>
        <button type="button" disabled={isSaving} onClick={() => saveRecord({ review_status: "approved" })}>
          Approve
        </button>
        <button type="button" disabled={isSaving} onClick={() => saveRecord({ review_status: "rejected" })}>
          Reject
        </button>
      </div>

      {entityType === "characters" && mergeTargets.length > 0 ? (
        <div className="merge-row">
          <select
            value={mergeTargetId}
            onChange={(event) => setMergeTargetId(event.target.value)}
            disabled={isSaving}
          >
            <option value="">Merge into...</option>
            {mergeTargets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.name}
              </option>
            ))}
          </select>
          <button type="button" disabled={isSaving || !mergeTargetId} onClick={mergeCharacter}>
            Merge
          </button>
        </div>
      ) : null}
    </article>
  );
}

function WikiRecordList({ emptyText, items, onSelect, selectedId }) {
  if (items.length === 0) {
    return <p className="empty-state">{emptyText}</p>;
  }

  return (
    <div className="wiki-list">
      {items.map((item) => (
        <button
          className={selectedId === item.id ? "wiki-list-button active" : "wiki-list-button"}
          key={item.id}
          type="button"
          onClick={() => onSelect(item)}
        >
          <strong>{item.name}</strong>
          {item.current_cultivation_level ? <small>{item.current_cultivation_level}</small> : null}
          {item.current_position ? <small>{item.current_position}</small> : null}
          {item.category ? <small>{item.category}</small> : null}
        </button>
      ))}
    </div>
  );
}

function WikiEvidence({ evidence }) {
  if (!evidence || evidence.length === 0) {
    return null;
  }

  return (
    <div className="evidence-list">
      <strong>Evidence</strong>
      {evidence.map((row) => (
        <p key={row.id}>
          {row.chapter ? `Chapter ${row.chapter.chapter_number}: ` : ""}
          {row.evidence_text}
        </p>
      ))}
    </div>
  );
}

function firstDescriptionChunk(description) {
  if (!description) {
    return "";
  }

  return description.split(/\n\s*\n/)[0].trim();
}

function initialsForName(name) {
  return (name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function chapterLabel(chapter) {
  return chapter ? `Chapter ${chapter.chapter_number}` : "Unknown chapter";
}

function relationshipLabel(relationship) {
  const type = relationship.relationship_type
    ? relationship.relationship_type.replace("_", " ")
    : "known";
  const chapter = relationship.chapter ? ` in Chapter ${relationship.chapter.chapter_number}` : "";
  return `${type.charAt(0).toUpperCase()}${type.slice(1)}${chapter}`;
}

function WikiAvatar({ name, size = "large" }) {
  return (
    <div className={`wiki-avatar ${size}`} aria-hidden="true">
      <span>{initialsForName(name)}</span>
    </div>
  );
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }

  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function WikiNovelOverview({ characters, items, novel, onOpenCharacters, onSelectCharacter, skills }) {
  const featuredCharacters = characters.slice(0, 4);
  const featuredSkills = skills.slice(0, 2);
  const featuredItems = items.slice(0, 2);
  const browseCards = [
    ["Characters", novel.approved_character_count, "View all characters", onOpenCharacters],
    ["Cultivation", novel.approved_progression_count, "Explore progression", null],
    ["Skills", novel.approved_skill_count, "View all skills", null],
    ["Items", novel.approved_item_count, "View all items", null],
    ["Organizations", 0, "Coming later", null],
    ["Places", 0, "Coming later", null],
    ["Timeline", 0, "Major events later", null],
  ];

  return (
    <article className="wiki-novel-page">
      <section className="wiki-novel-hero">
        <div className="wiki-novel-cover">
          <WikiAvatar name={novel.title} />
        </div>
        <div className="wiki-novel-info">
          <h1>{novel.title}</h1>
          <span className="wiki-novel-tag">Cultivation Novel</span>
          <div className="wiki-novel-meta">
            <span>Author: Unknown</span>
            <span>Status: Tracking</span>
            <span>Chapters Tracked: {formatNumber(novel.chapter_count)}</span>
          </div>
          <p>
            A structured public wiki built from reviewed extraction data. Browse approved
            characters, cultivation progression, skills, items, and future world entries.
          </p>
        </div>
      </section>

      <section className="wiki-stats-bar">
        <div>
          <strong>{formatNumber(novel.chapter_count)}</strong>
          <span>Chapters</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_character_count)}</strong>
          <span>Approved Characters</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_progression_count)}</strong>
          <span>Progression Facts</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_skill_count)}</strong>
          <span>Skills</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_item_count)}</strong>
          <span>Items</span>
        </div>
      </section>

      <section className="wiki-overview-grid">
        <div className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Main Characters</h2>
            <button className="wiki-text-link" type="button" onClick={onOpenCharacters}>
              View all characters
            </button>
          </div>
          <div className="wiki-character-card-grid">
            {featuredCharacters.map((character) => (
              <button
                className="wiki-character-card"
                key={character.id}
                type="button"
                onClick={() => onSelectCharacter(character)}
              >
                <WikiAvatar name={character.name} size="small" />
                <strong>{character.name}</strong>
                <span>{character.current_cultivation_level || character.current_position || "Character"}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="wiki-card">
          <h2>Data & Tracking Status</h2>
          <div className="wiki-status-list">
            <div>
              <span>Last updated</span>
              <strong>{formatDate(novel.updated_at)}</strong>
            </div>
            <div>
              <span>Approved entries</span>
              <strong>{formatNumber(novel.approved_entry_count)}</strong>
            </div>
            <div>
              <span>Pending review</span>
              <strong>{formatNumber(novel.pending_review_count)}</strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>Up to {formatNumber(novel.chapter_count)} chapters</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="wiki-card">
        <h2>Browse This Novel</h2>
        <div className="wiki-browse-grid">
          {browseCards.map(([label, count, subtitle, action]) => (
            <button
              className="wiki-browse-card"
              disabled={!action}
              key={label}
              type="button"
              onClick={action || undefined}
            >
              <span>{label.slice(0, 1)}</span>
              <div>
                <strong>{label}</strong>
                <small>
                  {formatNumber(count)} {subtitle}
                </small>
              </div>
            </button>
          ))}
        </div>
      </section>

      {(featuredSkills.length > 0 || featuredItems.length > 0) && (
        <section className="wiki-overview-grid compact">
          <div className="wiki-card">
            <h2>Featured Skills</h2>
            {featuredSkills.map((skill) => (
              <div className="wiki-mini-link" key={skill.id}>
                <strong>{skill.name}</strong>
                <span>{skill.category || "Skill"}</span>
              </div>
            ))}
          </div>
          <div className="wiki-card">
            <h2>Featured Items</h2>
            {featuredItems.map((item) => (
              <div className="wiki-mini-link" key={item.id}>
                <strong>{item.name}</strong>
                <span>{item.category || "Item"}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}

function WikiLandingPage({ novels, onLoadNovel }) {
  return (
    <article className="wiki-landing-page wiki-novel-library">
      <section className="wiki-library-header">
        <h1>Novels</h1>
        <p>Browse and explore cultivation novels with automatically extracted wiki data.</p>
      </section>

      <section className="wiki-library-toolbar">
        <input type="search" placeholder="Search novels..." />
        <select defaultValue="all">
          <option value="all">Status: All</option>
          <option value="tracking">Tracking</option>
          <option value="complete">Complete</option>
        </select>
        <select defaultValue="all">
          <option value="all">Chapters: All</option>
          <option value="short">Under 250</option>
          <option value="long">250+</option>
        </select>
        <select defaultValue="recent">
          <option value="recent">Sort: Recently Updated</option>
          <option value="title">Sort: Title</option>
        </select>
        <span>{formatNumber(novels.length)} novels</span>
      </section>

      <section className="wiki-card wiki-novel-table-card">
        {novels.length === 0 ? <p>No novels available yet.</p> : null}
        <div className="wiki-novel-table">
          <div className="wiki-novel-table-head">
            <span>Novel</span>
            <span>Author</span>
            <span>Status</span>
            <span>Chapters</span>
            <span>Last Updated</span>
            <span>Actions</span>
          </div>
          {novels.map((wikiNovel) => (
            <button
              className="wiki-novel-row"
              key={wikiNovel.id}
              type="button"
              onClick={() => onLoadNovel(wikiNovel.id)}
            >
              <div className="wiki-novel-row-title">
                <WikiAvatar name={wikiNovel.title} size="tiny" />
                <div>
                  <strong>{wikiNovel.title}</strong>
                  <small>Cultivation Novel</small>
                </div>
              </div>
              <span>Unknown</span>
              <span className="wiki-status-tag">Tracking</span>
              <strong>{formatNumber(wikiNovel.chapter_count)}</strong>
              <span>{formatDate(wikiNovel.updated_at)}</span>
              <span className="wiki-row-action">›</span>
            </button>
          ))}
        </div>
      </section>
    </article>
  );
}

function WikiCharacterBrowser({ characters, novel, onSelectCharacter }) {
  return (
    <article className="wiki-character-browser">
      <section className="wiki-library-header compact">
        <span className="wiki-novel-tag">{novel.title}</span>
        <h1>Characters</h1>
        <p>Browse approved characters for this novel.</p>
      </section>

      <section className="wiki-card">
        <div className="wiki-card-heading">
          <h2>All Characters</h2>
          <span>{formatNumber(characters.length)} approved</span>
        </div>
        {characters.length === 0 ? <p>No approved characters yet.</p> : null}
        <div className="wiki-character-browser-grid">
          {characters.map((character) => (
            <button
              className="wiki-character-browser-card"
              key={character.id}
              type="button"
              onClick={() => onSelectCharacter(character)}
            >
              <WikiAvatar name={character.name} size="small" />
              <div>
                <strong>{character.name}</strong>
                <span>{character.current_cultivation_level || character.current_position || "Character"}</span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </article>
  );
}

function WikiCharacterDetail({ character, relatedCharacters = [], onSelectRelated }) {
  if (!character) {
    return (
      <section className="wiki-empty-panel">
        <h2>Select a character</h2>
        <p>Choose an approved character from the sidebar to view their public wiki page.</p>
      </section>
    );
  }

  const displayDescription = firstDescriptionChunk(character.description);
  const progressionEvents = [...(character.progression_events || [])].sort((first, second) => {
    const firstChapter = first.chapter ? first.chapter.chapter_number : 0;
    const secondChapter = second.chapter ? second.chapter.chapter_number : 0;
    return secondChapter - firstChapter;
  });
  const currentProgression = progressionEvents.find(
    (event) =>
      character.current_cultivation_level &&
      event.new_value &&
      event.new_value.toLowerCase() === character.current_cultivation_level.toLowerCase()
  );
  const shownRelatedCharacters = relatedCharacters
    .filter((related) => related.id !== character.id)
    .slice(0, 3);

  return (
    <article className="wiki-character-page">
      <section className="wiki-hero-card">
        <div className="wiki-portrait">
          <WikiAvatar name={character.name} />
        </div>

        <div className="wiki-hero-main">
          <div className="wiki-title-row">
            <h1>{character.name}</h1>
            <span className="wiki-title-mark">Qi</span>
          </div>

          <div className="wiki-fact-grid">
            <div className="wiki-fact">
              <span className="wiki-fact-icon">C</span>
              <div>
                <small>Current Cultivation</small>
                <strong>{character.current_cultivation_level || "Unknown"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">P</span>
              <div>
                <small>Current Position</small>
                <strong>{character.current_position || "Unknown"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">B</span>
              <div>
                <small>First Mentioned</small>
                <strong>{chapterLabel(character.first_mentioned_chapter)}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">A</span>
              <div>
                <small>Aliases</small>
                <strong>
                  {character.aliases && character.aliases.length > 0
                    ? character.aliases.map((alias) => alias.alias).join(", ")
                    : "N/A"}
                </strong>
              </div>
            </div>
          </div>

          {displayDescription ? <p className="wiki-description">{displayDescription}</p> : null}
        </div>
      </section>

      <section className="wiki-content-grid">
        <div className="wiki-card wiki-progression-card">
          <h2>Cultivation Progression</h2>
          {progressionEvents.length === 0 ? <p>No approved progression yet.</p> : null}
          <div className="wiki-timeline">
            {progressionEvents.map((event) => {
              const isCurrent = currentProgression ? currentProgression.id === event.id : false;

              return (
                <article className={isCurrent ? "wiki-timeline-row active" : "wiki-timeline-row"} key={event.id}>
                  <span className="wiki-timeline-dot" />
                  <div>
                    <small>{chapterLabel(event.chapter)}</small>
                    <strong>{event.new_value}</strong>
                    {event.old_value ? <p>From {event.old_value}</p> : null}
                  </div>
                  {isCurrent ? <span className="wiki-stage-pill">Current Stage</span> : null}
                </article>
              );
            })}
          </div>
        </div>

        <div className="wiki-side-stack">
          <section className="wiki-card">
            <h2>Skills</h2>
            {character.skills && character.skills.length > 0 ? (
              character.skills.map((relationship) => (
                <article className="wiki-skill-row" key={relationship.id}>
                  <span className="wiki-skill-icon">F</span>
                  <div>
                    <strong>{relationship.skill ? relationship.skill.name : "Unknown skill"}</strong>
                    <p>{relationshipLabel(relationship)}</p>
                  </div>
                </article>
              ))
            ) : (
              <p>No approved skills yet.</p>
            )}
          </section>

          <section className="wiki-card">
            <h2>Related Characters</h2>
            {shownRelatedCharacters.length === 0 ? <p>No related characters yet.</p> : null}
            {shownRelatedCharacters.map((related) => (
              <button
                className="wiki-related-row"
                key={related.id}
                type="button"
                onClick={() => onSelectRelated(related)}
              >
                <WikiAvatar name={related.name} size="small" />
                <span>{related.name}</span>
                <small>{related.current_cultivation_level || related.current_position || ""}</small>
              </button>
            ))}
          </section>
        </div>
      </section>
    </article>
  );
}

function WikiSkillDetail({ skill }) {
  if (!skill) {
    return <p>Select a skill to read its wiki page.</p>;
  }

  return (
    <article className="wiki-detail">
      <h3>{skill.name}</h3>

      {skill.category ? (
        <div className="meta-lines">
          <span>Category: {skill.category}</span>
        </div>
      ) : null}

      {skill.aliases && skill.aliases.length > 0 ? (
        <div className="alias-list">
          <strong>Aliases</strong>
          {skill.aliases.map((alias) => (
            <span key={alias.id}>{alias.alias}</span>
          ))}
        </div>
      ) : null}

      {skill.description ? <p>{skill.description}</p> : null}

      <WikiEvidence evidence={skill.evidence} />
    </article>
  );
}

function WikiItemDetail({ item }) {
  if (!item) {
    return <p>Select an item to read its wiki page.</p>;
  }

  return (
    <article className="wiki-detail">
      <h3>{item.name}</h3>

      {item.category ? (
        <div className="meta-lines">
          <span>Category: {item.category}</span>
        </div>
      ) : null}

      {item.description ? <p>{item.description}</p> : null}

      <WikiEvidence evidence={item.evidence} />
    </article>
  );
}

function WikiPanel({
  characters,
  items,
  page,
  loading,
  novel,
  novels,
  onLoadNovel,
  onOpenAdmin,
  onSelectCharacter,
  selectedCharacter,
  selectedNovelId,
  skills,
}) {
  const navigate = useNavigate();
  const trackedNovel = novel;
  const activeSection = !trackedNovel ? "Novels" : page === "Character" ? "Characters" : page;
  const globalNav = ["Novels", "Recent Updates", "Bookmarks", "About"];
  const novelNav = ["Novels", "Overview", "Characters", "Cultivation", "Skills", "Items", "Organizations", "Places", "Timeline"];

  function openNovel(novelId) {
    navigate(`/wiki/novels/${novelId}`);
  }

  function openCharacters() {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters`);
    }
  }

  function openCharacter(character) {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters/${character.id}`);
    }
  }

  function handleNav(label) {
    if (label === "Novels") {
      navigate("/wiki/novels");
      return;
    }

    if (!trackedNovel) {
      return;
    }

    if (label === "Overview") {
      navigate(`/wiki/novels/${trackedNovel.id}`);
      return;
    }

    if (label === "Characters") {
      openCharacters();
    }
  }

  return (
    <section className="wiki-app">
      <aside className="wiki-sidebar">
        <div className="wiki-brand">
          <div className="wiki-logo">NW</div>
          <strong>Cultivation Wiki</strong>
          <span>Explore the Dao</span>
        </div>

        <input className="wiki-sidebar-search" type="search" placeholder="Search wiki..." />

        <nav className="wiki-nav">
          {(trackedNovel ? novelNav : globalNav).map((label) => (
            <button
              className={label === activeSection ? "active" : ""}
              disabled={
                Boolean(trackedNovel) &&
                !["Novels", "Overview", "Characters"].includes(label)
              }
              key={label}
              type="button"
              onClick={() => handleNav(label)}
            >
              <span>{label.slice(0, 1)}</span>
              {label}
            </button>
          ))}
        </nav>

        <div className="wiki-sidebar-section">
          <div className="wiki-sidebar-title">
            <span>{trackedNovel ? "Selected Novel" : "Novel Context"}</span>
            <button type="button" onClick={onOpenAdmin}>
              Admin
            </button>
          </div>
          {trackedNovel ? (
            <button
              className="wiki-tracked-novel active"
              type="button"
              onClick={() => openNovel(trackedNovel.id)}
            >
              <WikiAvatar name={trackedNovel.title} size="tiny" />
              <span>{trackedNovel.title}</span>
              <small>{trackedNovel.approved_character_count} characters</small>
            </button>
          ) : (
            <p className="wiki-sidebar-context-empty">
              Select a novel from the main list to browse its characters, skills, and progression.
            </p>
          )}
        </div>
      </aside>

      <div className="wiki-main">
        <header className="wiki-topbar">
          <div className="wiki-breadcrumb">
            <Link to="/wiki/novels">Home</Link>
            <span>/</span>
            <Link to="/wiki/novels">Novels</Link>
            {trackedNovel ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}`}>{trackedNovel.title}</Link>
              </>
            ) : null}
            {page === "Characters" ? (
              <>
                <span>/</span>
                <strong>Characters</strong>
              </>
            ) : null}
            {page === "Character" && selectedCharacter ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/characters`}>Characters</Link>
                <span>/</span>
                <strong>{selectedCharacter.name}</strong>
              </>
            ) : null}
          </div>
          <input className="wiki-search" type="search" placeholder="Search characters, novels, skills..." />
        </header>

        <div className="wiki-content">
          {!trackedNovel ? (
            <WikiLandingPage novels={novels} onLoadNovel={openNovel} />
          ) : null}

          {loading ? <p className="wiki-loading">Loading wiki data...</p> : null}

          {trackedNovel ? (
            <>
              <section className="wiki-browser-strip">
                <div>
                  <strong>{trackedNovel.title}</strong>
                  <span>
                    {trackedNovel.approved_character_count} characters / {trackedNovel.approved_skill_count} skills /{" "}
                    {trackedNovel.approved_item_count} items
                  </span>
                </div>
                <div className="wiki-entity-tabs">
                  <select
                    value={selectedCharacter ? selectedCharacter.id : ""}
                    onChange={(event) => {
                      if (!event.target.value) {
                        navigate(`/wiki/novels/${trackedNovel.id}`);
                        return;
                      }

                      const character = characters.find((item) => item.id === Number(event.target.value));
                      if (character) {
                        openCharacter(character);
                      }
                    }}
                  >
                    <option value="">Select character...</option>
                    {characters.map((character) => (
                      <option key={character.id} value={character.id}>
                        {character.name}
                      </option>
                    ))}
                  </select>
                </div>
              </section>

              {page === "Character" && selectedCharacter ? (
                <WikiCharacterDetail
                  character={selectedCharacter}
                  relatedCharacters={characters}
                  onSelectRelated={openCharacter}
                />
              ) : null}

              {page === "Characters" ? (
                <WikiCharacterBrowser
                  characters={characters}
                  novel={trackedNovel}
                  onSelectCharacter={openCharacter}
                />
              ) : null}

              {page === "Overview" ? (
                <WikiNovelOverview
                  characters={characters}
                  items={items}
                  novel={trackedNovel}
                  onOpenCharacters={openCharacters}
                  onSelectCharacter={openCharacter}
                  skills={skills}
                />
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function WikiNovelRoute({ items, loading, loadNovel, loadCharacter, novel, novels, onOpenAdmin, setMessage, ...props }) {
  const { novelId, characterId } = useParams();
  const numericNovelId = Number(novelId);
  const numericCharacterId = characterId ? Number(characterId) : null;
  const page = numericCharacterId ? "Character" : props.page;

  React.useEffect(() => {
    if (numericNovelId && (!novel || novel.id !== numericNovelId)) {
      loadNovel(numericNovelId).catch((error) => setMessage(error.message));
    }
  }, [numericNovelId, novel, loadNovel, setMessage]);

  React.useEffect(() => {
    if (!numericCharacterId || props.selectedCharacter?.id === numericCharacterId) {
      return;
    }

    const listedCharacter = props.characters.find((character) => character.id === numericCharacterId);
    if (listedCharacter) {
      loadCharacter(listedCharacter).catch((error) => setMessage(error.message));
    }
  }, [numericCharacterId, props.characters, props.selectedCharacter, loadCharacter, setMessage]);

  return (
    <WikiPanel
      {...props}
      items={items}
      loading={loading}
      novel={novel}
      novels={novels}
      onLoadNovel={loadNovel}
      onOpenAdmin={onOpenAdmin}
      onSelectCharacter={loadCharacter}
      page={page}
    />
  );
}

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeView = location.pathname.startsWith("/admin") ? "admin" : "wiki";
  const [novels, setNovels] = React.useState([]);
  const [selectedNovelId, setSelectedNovelId] = React.useState(null);
  const [chapterResult, setChapterResult] = React.useState(null);
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [message, setMessage] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [isBatchExtracting, setIsBatchExtracting] = React.useState(false);
  const [extractingChapterId, setExtractingChapterId] = React.useState(null);
  const [extractedData, setExtractedData] = React.useState(null);
  const [wikiCharacters, setWikiCharacters] = React.useState([]);
  const [wikiItems, setWikiItems] = React.useState([]);
  const [wikiLoading, setWikiLoading] = React.useState(false);
  const [wikiNovel, setWikiNovel] = React.useState(null);
  const [wikiNovels, setWikiNovels] = React.useState([]);
  const [wikiSelectedCharacter, setWikiSelectedCharacter] = React.useState(null);
  const [wikiSelectedItem, setWikiSelectedItem] = React.useState(null);
  const [wikiSelectedNovelId, setWikiSelectedNovelId] = React.useState(null);
  const [wikiSelectedSkill, setWikiSelectedSkill] = React.useState(null);
  const [wikiSkills, setWikiSkills] = React.useState([]);

  async function loadNovels() {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels`);
    setNovels(data);
  }

  async function loadWikiNovels() {
    const data = await fetchJson(`${API_BASE_URL}/wiki/novels`);
    setWikiNovels(data);
  }

  async function loadWikiNovel(novelId) {
    setWikiLoading(true);
    setWikiSelectedNovelId(novelId);
    setWikiSelectedCharacter(null);
    setWikiSelectedSkill(null);
    setWikiSelectedItem(null);

    try {
      const [novelData, charactersData, skillsData, itemsData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/characters`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/skills`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/items`),
      ]);

      setWikiNovel(novelData);
      setWikiCharacters(charactersData);
      setWikiSkills(skillsData);
      setWikiItems(itemsData);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiCharacter(character) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/characters/${character.id}`);
      setWikiSelectedCharacter(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiSkill(skill) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/skills/${skill.id}`);
      setWikiSelectedSkill(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiItem(item) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/items/${item.id}`);
      setWikiSelectedItem(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadChapters(novelId) {
    setSelectedNovelId(novelId);
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters`);
    setChapterResult(data);
    await loadExtractedData(novelId);
  }

  async function loadExtractedData(novelId) {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extracted-data`);
    setExtractedData(data);
  }

  async function handleProcessNovel() {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setIsProcessing(true);
    setMessage("");

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${selectedNovelId}/process`, {
        method: "POST",
      });

      setExtractedData(data);
      setMessage(`Processed ${data.novel.title} with placeholder extraction.`);
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleExtractChapter(chapterId) {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setExtractingChapterId(chapterId);
    setMessage("");

    try {
      const data = await fetchJson(
        `${API_BASE_URL}/admin/novels/${selectedNovelId}/chapters/${chapterId}/extract`,
        {
          method: "POST",
        }
      );

      setExtractedData(data);
      setMessage(buildExtractionMessage(data));
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setExtractingChapterId(null);
    }
  }

  async function handleExtractFirstFifteen() {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setIsBatchExtracting(true);
    setMessage("Extracting first 15 chapters in order...");

    try {
      const data = await fetchJson(
        `${API_BASE_URL}/admin/novels/${selectedNovelId}/extract-first-15`,
        {
          method: "POST",
        }
      );

      setExtractedData(data);
      setMessage(buildBatchExtractionMessage(data));
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsBatchExtracting(false);
    }
  }

  function updateExtractedRecord(entityType, updatedRecord) {
    setExtractedData((currentData) => {
      if (!currentData) {
        return currentData;
      }

      return {
        ...currentData,
        [entityType]: currentData[entityType].map((record) =>
          record.id === updatedRecord.id ? updatedRecord : record
        ),
      };
    });
    setMessage("Review saved.");
  }

  async function handleMergedCharacter() {
    if (selectedNovelId) {
      await loadExtractedData(selectedNovelId);
    }

    setMessage("Characters merged.");
  }

  function buildExtractionMessage(data) {
    if (!data.summary || !data.extracted_chapter) {
      return "AI extraction finished for one chapter. Review the pending records below.";
    }

    const summary = data.summary;
    const chapter = data.extracted_chapter;
    const characterCount = summary.characters_created + summary.characters_updated;
    const skillCount = summary.skills_created + summary.skills_updated;
    const itemCount = summary.items_created + summary.items_updated;
    const characterSkillCount = summary.character_skills_created || 0;

    return (
      `Chapter ${chapter.chapter_number} extracted: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${summary.life_events_created} life events, ${summary.events_created} timeline facts.`
    );
  }

  function buildBatchExtractionMessage(data) {
    if (!data.summary || !data.extracted_chapter_count) {
      return "Batch extraction finished. Review the pending records below.";
    }

    const summary = data.summary;
    const characterCount = summary.characters_created + summary.characters_updated;
    const skillCount = summary.skills_created + summary.skills_updated;
    const itemCount = summary.items_created + summary.items_updated;
    const characterSkillCount = summary.character_skills_created || 0;

    return (
      `Extracted ${data.extracted_chapter_count} chapters: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${summary.life_events_created} life events.`
    );
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!file) {
      setMessage("Choose a .txt file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);

    setIsUploading(true);
    setMessage("");

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/upload`, {
        method: "POST",
        body: formData,
      });

      setMessage(`Uploaded ${data.novel.title} with ${data.chapter_count} chapters.`);
      setTitle("");
      setFile(null);
      event.target.reset();
      await loadNovels();
      await loadChapters(data.novel.id);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsUploading(false);
    }
  }

  React.useEffect(() => {
    loadNovels().catch((error) => setMessage(error.message));
    loadWikiNovels().catch((error) => setMessage(error.message));
  }, []);

  return (
    <main className={activeView === "wiki" ? "app-shell wiki-shell" : "app-shell"}>
      <section className="page-header">
        <p className="eyebrow">{activeView === "admin" ? "Admin MVP" : "Public Wiki"}</p>
        <h1>{activeView === "admin" ? "NovelWiki Upload Verification" : "NovelWiki"}</h1>
        <div className="view-toggle">
          <button
            className={activeView === "admin" ? "active" : ""}
            type="button"
            onClick={() => navigate("/admin")}
          >
            Admin
          </button>
          <button
            className={activeView === "wiki" ? "active" : ""}
            type="button"
            onClick={() => {
              navigate("/wiki/novels");
              loadWikiNovels().catch((error) => setMessage(error.message));
            }}
          >
            Wiki
          </button>
        </div>
      </section>

      {message ? <p className="message">{message}</p> : null}

      {activeView === "wiki" ? (
        <Routes>
          <Route path="/" element={<Navigate to="/wiki/novels" replace />} />
          <Route path="/wiki" element={<Navigate to="/wiki/novels" replace />} />
          <Route
            path="/wiki/novels"
            element={
              <WikiPanel
                characters={[]}
                items={[]}
                loading={wikiLoading}
                novel={null}
                novels={wikiNovels}
                onLoadNovel={loadWikiNovel}
                onOpenAdmin={() => navigate("/admin")}
                onSelectCharacter={loadWikiCharacter}
                page="Novels"
                selectedCharacter={null}
                selectedNovelId={null}
                skills={[]}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Overview"
                selectedCharacter={null}
                selectedNovelId={wikiSelectedNovelId}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/characters"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Characters"
                selectedCharacter={null}
                selectedNovelId={wikiSelectedNovelId}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/characters/:characterId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Characters"
                selectedCharacter={wikiSelectedCharacter}
                selectedNovelId={wikiSelectedNovelId}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
        </Routes>
      ) : (
        <>
          <section className="panel">
            <h2>Upload .txt Novel</h2>
            <form className="upload-form" onSubmit={handleUpload}>
              <label>
                Novel title
                <input
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Optional, defaults to file name"
                />
              </label>

              <label>
                Novel file
                <input
                  type="file"
                  accept=".txt,text/plain"
                  onChange={(event) => setFile(event.target.files[0])}
                />
              </label>

              <button type="submit" disabled={isUploading}>
                {isUploading ? "Uploading..." : "Upload and Split"}
              </button>
            </form>
          </section>

          <section className="layout">
            <aside className="panel novel-list">
              <h2>Uploaded Novels</h2>
              {novels.length === 0 ? <p>No novels uploaded yet.</p> : null}
              {novels.map((novel) => (
                <button
                  className={selectedNovelId === novel.id ? "novel-button active" : "novel-button"}
                  key={novel.id}
                  type="button"
                  onClick={() => loadChapters(novel.id).catch((error) => setMessage(error.message))}
                >
                  <span>{novel.title}</span>
                  <small>{novel.chapter_count} chapters</small>
                  <small>Status: {novel.status}</small>
                </button>
              ))}
            </aside>

            <div className="content-stack">
              <section className="panel chapter-panel">
                <h2>Chapter Verification</h2>
                {!chapterResult ? <p>Select a novel to inspect chapter metadata.</p> : null}
                {chapterResult ? (
                  <>
                    <div className="summary-row">
                      <strong>{chapterResult.novel.title}</strong>
                      <span>{chapterResult.chapters.length} chapters</span>
                    </div>
                    <div className="chapter-table">
                      {chapterResult.chapters.map((chapter) => (
                        <article className="chapter-row" key={chapter.id}>
                          <div>
                            <strong>
                              {chapter.chapter_number}. {chapter.title}
                            </strong>
                            <p>{chapter.preview}</p>
                          </div>
                          <div className="chapter-actions">
                            <span>{chapter.character_count.toLocaleString()} chars</span>
                            <button
                              type="button"
                              disabled={isBatchExtracting || extractingChapterId === chapter.id}
                              onClick={() => handleExtractChapter(chapter.id)}
                            >
                              {extractingChapterId === chapter.id ? "Extracting..." : "AI Extract"}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  </>
                ) : null}
              </section>

              <section className="panel extraction-panel">
                <div className="panel-header">
                  <h2>Extraction Pipeline</h2>
                  <div className="button-row">
                    <button
                      type="button"
                      disabled={!selectedNovelId || isProcessing || isBatchExtracting}
                      onClick={handleProcessNovel}
                    >
                      {isProcessing ? "Processing..." : "Run Placeholder Processing"}
                    </button>
                    <button
                      type="button"
                      disabled={!selectedNovelId || isBatchExtracting || extractingChapterId}
                      onClick={handleExtractFirstFifteen}
                    >
                      {isBatchExtracting ? "Extracting 1-15..." : "Extract First 15"}
                    </button>
                  </div>
                </div>

                {!selectedNovelId ? <p>Select a novel to run placeholder extraction.</p> : null}
                {selectedNovelId && !extractedData ? <p>No extracted data loaded yet.</p> : null}

                {extractedData ? (
                  <div className="extraction-grid">
                    <section>
                      <h3>Characters</h3>
                      {extractedData.characters.map((character) => (
                        <ReviewRecord
                          entityType="characters"
                          fields={["name", "description"]}
                          key={character.id}
                          mergeTargets={extractedData.characters.filter((target) => target.id !== character.id)}
                          record={character}
                          onMerged={handleMergedCharacter}
                          onSaved={(updatedRecord) => updateExtractedRecord("characters", updatedRecord)}
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Skills</h3>
                      {extractedData.skills.map((skill) => (
                        <ReviewRecord
                          entityType="skills"
                          fields={["name", "category", "description"]}
                          key={skill.id}
                          record={skill}
                          onSaved={(updatedRecord) => updateExtractedRecord("skills", updatedRecord)}
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Items</h3>
                      {extractedData.items.map((item) => (
                        <ReviewRecord
                          entityType="items"
                          fields={["name", "category", "description"]}
                          key={item.id}
                          record={item}
                          onSaved={(updatedRecord) => updateExtractedRecord("items", updatedRecord)}
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Timeline Facts</h3>
                      {extractedData.events.map((event) => (
                        <ReviewRecord
                          entityType="events"
                          fields={["event_type", "title", "description"]}
                          key={event.id}
                          record={event}
                          onSaved={(updatedRecord) => updateExtractedRecord("events", updatedRecord)}
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Progression</h3>
                      {extractedData.progression_events.map((event) => (
                        <ReviewRecord
                          entityType="progression_events"
                          fields={["progression_type", "old_value", "new_value", "description"]}
                          key={event.id}
                          record={event}
                          onSaved={(updatedRecord) =>
                            updateExtractedRecord("progression_events", updatedRecord)
                          }
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Character Skills</h3>
                      {extractedData.character_skills.map((relationship) => (
                        <ReviewRecord
                          entityType="character_skills"
                          fields={["relationship_type", "description"]}
                          key={relationship.id}
                          record={relationship}
                          onSaved={(updatedRecord) =>
                            updateExtractedRecord("character_skills", updatedRecord)
                          }
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Character Items</h3>
                      {extractedData.character_items.map((relationship) => (
                        <ReviewRecord
                          entityType="character_items"
                          fields={["relationship_type", "description"]}
                          key={relationship.id}
                          record={relationship}
                          onSaved={(updatedRecord) =>
                            updateExtractedRecord("character_items", updatedRecord)
                          }
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Life Events</h3>
                      {extractedData.life_events.map((event) => (
                        <ReviewRecord
                          entityType="life_events"
                          fields={["event_type", "description", "reason"]}
                          key={event.id}
                          record={event}
                          onSaved={(updatedRecord) => updateExtractedRecord("life_events", updatedRecord)}
                        />
                      ))}
                    </section>

                    {extractedData.characters.length === 0 &&
                    extractedData.skills.length === 0 &&
                    extractedData.items.length === 0 &&
                    extractedData.events.length === 0 &&
                    extractedData.progression_events.length === 0 &&
                    extractedData.character_skills.length === 0 &&
                    extractedData.character_items.length === 0 &&
                    extractedData.life_events.length === 0 ? (
                      <p className="empty-state">No extracted records yet.</p>
                    ) : null}
                  </div>
                ) : null}
              </section>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
);
