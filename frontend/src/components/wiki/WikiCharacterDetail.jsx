import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import {
  chapterLabel,
  firstDescriptionChunk,
  formatCultivationValue,
  formatMetadataValue,
  relationshipLabel,
} from "../../utils/wikiFormat.js";

export default function WikiCharacterDetail({
  character,
  onOpenCultivation,
  onSelectItem,
  onSelectRelated,
  onSelectSkill,
  relatedCharacters = [],
}) {
  if (!character) {
    return (
      <section className="wiki-empty-panel">
        <h2>Select a character</h2>
        <p>Choose an approved character from the sidebar to view their public wiki page.</p>
      </section>
    );
  }

  const displayDescription = firstDescriptionChunk(character.description);
  const aliases = character.aliases || [];
  const skills = character.skills || [];
  const items = character.items || [];
  const lifeEvents = character.life_events || [];
  const evidence = character.evidence || [];
  const currentCultivation = formatCultivationValue(character.current_cultivation_level);
  const currentCultivationEvent = (character.progression_events || []).find(
    (event) =>
      character.current_cultivation_level &&
      event.new_value &&
      formatCultivationValue(event.new_value).toLowerCase() === currentCultivation.toLowerCase()
  );
  const shownRelatedCharacters = relatedCharacters
    .filter((related) => related.id !== character.id)
    .filter((related) => {
      const characterSkillNames = new Set(
        skills
          .map((relationship) => relationship.skill?.name)
          .filter(Boolean)
          .map((name) => name.toLowerCase())
      );

      return (related.skills || []).some((relationship) =>
        characterSkillNames.has((relationship.skill?.name || "").toLowerCase())
      );
    })
    .slice(0, 4);
  const shownSkills = skills.slice(0, 4);
  const shownItems = items.slice(0, 4);
  const shownEvidence = evidence.slice(0, 3);
  const shownLifeEvents = lifeEvents.slice(0, 3);
  const titles = splitTitles(character.titles);
  const latestTitle = titles[titles.length - 1] || "";
  const quickFacts = [
    {
      icon: "C",
      label: "Current Cultivation",
      value: currentCultivation || "Unknown",
      action: (
        <button className="wiki-inline-link" type="button" onClick={onOpenCultivation}>
          View full progression
        </button>
      ),
    },
    { icon: "P", label: "Current Position", value: formatMetadataValue(character.current_position, "current_position") },
    { icon: "M", label: "First Mentioned", value: chapterLabel(character.first_mentioned_chapter) },
    { icon: "A", label: "First Appeared", value: chapterLabel(character.first_appeared_chapter) },
    { icon: "G", label: "Gender", value: formatMetadataValue(character.gender, "gender") },
    { icon: "R", label: "Race / Species", value: formatMetadataValue(character.race_or_species, "race_or_species") },
    { icon: "O", label: "Origin", value: formatMetadataValue(character.origin, "origin") },
    { icon: "F", label: "Affiliation", value: formatMetadataValue(character.faction_or_affiliation, "faction_or_affiliation") },
    { icon: "S", label: "Status", value: formatMetadataValue(character.status, "status") },
    { icon: "T", label: "Latest Title", value: formatMetadataValue(latestTitle, "titles") },
    { icon: "Y", label: "Age", value: formatMetadataValue(character.age_text, "age_text") },
  ].filter((fact) => fact.value);

  function shortEvidence(text) {
    const normalized = (text || "").replace(/\s+/g, " ").trim();

    if (normalized.length <= 140) {
      return normalized;
    }

    return `${normalized.slice(0, 137).trim()}...`;
  }

  function splitTitles(titlesText) {
    return (titlesText || "")
      .split(/[\n,;]+/)
      .map((title) => title.trim())
      .filter(Boolean);
  }

  return (
    <article className="wiki-character-page">
      <section className="wiki-character-profile">
        <div className="wiki-character-portrait">
          <WikiAvatar name={character.name} />
        </div>

        <div className="wiki-character-profile-main">
          <div className="wiki-title-row">
            <h1>{character.name}</h1>
          </div>

          <p className="wiki-character-subtitle">
            {formatMetadataValue(character.current_position, "current_position") || "Character"}
            {currentCultivation ? ` • ${currentCultivation}` : ""}
          </p>
          {displayDescription ? <p className="wiki-description">{displayDescription}</p> : null}

          <div className="wiki-character-status-row">
            <span>{skills.length} skills</span>
            <span>{items.length} items</span>
            <span>{lifeEvents.length} life events</span>
          </div>
        </div>
      </section>

      <section className="wiki-character-fact-strip">
        {quickFacts.map((fact) => (
          <div className="wiki-character-fact-card" key={fact.label}>
            <span className="wiki-fact-icon">{fact.icon}</span>
            <div>
              <small>{fact.label}</small>
              <strong>{fact.value}</strong>
              {fact.action}
            </div>
          </div>
        ))}
      </section>

      <section className="wiki-character-layout">
        <div className="wiki-character-main-stack">
          <section className="wiki-card">
            <h2>About</h2>
            <p className="wiki-section-copy">
              {displayDescription || "No character description has been added yet."}
            </p>
          </section>

          <section className="wiki-card">
            <div className="wiki-card-heading">
              <h2>Aliases</h2>
              <span>{aliases.length}</span>
            </div>
            {aliases.length > 0 ? (
              <div className="wiki-alias-cloud">
                {aliases.map((alias) => (
                  <span key={alias.id}>{alias.alias}</span>
                ))}
              </div>
            ) : (
              <p className="wiki-muted-copy">No aliases recorded yet.</p>
            )}
          </section>

          <section className="wiki-card wiki-current-cultivation-card">
            <div>
              <h2>Current Cultivation</h2>
              <strong>{currentCultivation || "Unknown"}</strong>
              {currentCultivationEvent?.chapter ? (
                <p>Confirmed in {chapterLabel(currentCultivationEvent.chapter)}.</p>
              ) : (
                <p>Full progression history is available on the cultivation timeline.</p>
              )}
            </div>
            <button className="wiki-outline-link" type="button" onClick={onOpenCultivation}>
              View full progression
            </button>
          </section>

          <section className="wiki-card">
            <div className="wiki-card-heading">
              <h2>Skills Summary</h2>
              {skills.length > shownSkills.length ? <span>{skills.length - shownSkills.length} more</span> : null}
            </div>
            {shownSkills.length > 0 ? (
              <div className="wiki-summary-list">
                {shownSkills.map((relationship) => (
                  <button
                    className="wiki-summary-row"
                    disabled={!relationship.skill}
                    key={relationship.id}
                    type="button"
                    onClick={() => onSelectSkill(relationship.skill)}
                  >
                    <span className="wiki-skill-icon small">S</span>
                    <div>
                      <strong>{relationship.skill ? relationship.skill.name : "Unknown skill"}</strong>
                      <p>{relationshipLabel(relationship)}</p>
                    </div>
                    <span className="wiki-row-action">›</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="wiki-muted-copy">No skills recorded yet.</p>
            )}
          </section>

          <section className="wiki-card">
            <div className="wiki-card-heading">
              <h2>Evidence Highlights</h2>
              {evidence.length > shownEvidence.length ? <span>{evidence.length - shownEvidence.length} more</span> : null}
            </div>
            {shownEvidence.length > 0 ? (
              <div className="wiki-evidence-highlight-grid">
                {shownEvidence.map((row) => (
                  <article className="wiki-evidence-highlight" key={row.id}>
                    <p>"{shortEvidence(row.evidence_text)}"</p>
                    <small>{chapterLabel(row.chapter)}</small>
                  </article>
                ))}
              </div>
            ) : (
              <p className="wiki-muted-copy">No evidence snippets recorded yet.</p>
            )}
          </section>
        </div>

        <aside className="wiki-character-side-stack">
          <section className="wiki-card">
            <h2>Items Summary</h2>
            {shownItems.length > 0 ? (
              <div className="wiki-compact-list">
                {shownItems.map((relationship) => (
                  <button
                    className="wiki-compact-row"
                    disabled={!relationship.item || !onSelectItem}
                    key={relationship.id}
                    type="button"
                    onClick={() => onSelectItem(relationship.item)}
                  >
                    <strong>{relationship.item ? relationship.item.name : "Unknown item"}</strong>
                    <span>{relationshipLabel(relationship)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="wiki-muted-copy">No items recorded yet.</p>
            )}
          </section>

          <section className="wiki-card wiki-spoiler-card">
            <details>
              <summary>
                <span>Life Events</span>
                <small>{lifeEvents.length} recorded</small>
              </summary>
              {shownLifeEvents.length > 0 ? (
                <div className="wiki-compact-list">
                  {shownLifeEvents.map((event) => (
                    <article className="wiki-life-event-row" key={event.id}>
                      <strong>{event.event_type.replace("_", " ")}</strong>
                      <span>{chapterLabel(event.chapter)}</span>
                      {event.description ? <p>{event.description}</p> : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="wiki-muted-copy">No life events recorded yet.</p>
              )}
            </details>
          </section>

          {shownRelatedCharacters.length > 0 ? (
            <section className="wiki-card">
              <h2>Related Characters</h2>
              {shownRelatedCharacters.map((related) => (
                <button
                  className="wiki-related-row"
                  key={related.id}
                  type="button"
                  onClick={() => onSelectRelated(related)}
                >
                  <WikiAvatar name={related.name} size="small" />
                  <span>{related.name}</span>
                  <small>
                    {related.current_cultivation_level
                      ? formatCultivationValue(related.current_cultivation_level)
                      : related.current_position || ""}
                  </small>
                </button>
              ))}
            </section>
          ) : null}
        </aside>
      </section>
    </article>
  );
}
