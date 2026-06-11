import React from "react";
import {
  Activity,
  BadgeCheck,
  BookOpen,
  Building2,
  Calendar,
  Crown,
  Dna,
  MapPin,
  Package,
  Sparkles,
  UserRound,
  Zap,
} from "lucide-react";
import WikiAvatar from "./WikiAvatar.jsx";
import { ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemsIndex.jsx";
import { skillCategoryClass } from "./WikiSkillsIndex.jsx";
import {
  chapterLabel,
  cleanChapterTitle,
  firstDescriptionChunk,
  formatCultivationValue,
  formatMetadataValue,
} from "../../utils/wikiFormat.js";

export default function WikiCharacterDetail({
  character,
  onOpenCultivation,
  onOpenItems,
  onOpenSkills,
  onSelectItem,
  onSelectSkill,
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
  const evidence = character.evidence || [];
  const currentCultivation = formatCultivationValue(character.current_cultivation_level);
  const cultivationEvents = (character.progression_events || []).filter(
    (event) => event.progression_type === "cultivation_level" && event.new_value
  );
  const currentCultivationEvent = (character.progression_events || []).find(
    (event) =>
      character.current_cultivation_level &&
      event.new_value &&
      formatCultivationValue(event.new_value).toLowerCase() === currentCultivation.toLowerCase()
  );
  const shownSkills = skills.slice(0, 5);
  const shownItems = items.slice(0, 5);
  const shownEvidence = evidence.slice(0, 3);
  const titles = splitTitles(character.titles);
  const latestTitle = titles[titles.length - 1] || "";
  const [aboutExpanded, setAboutExpanded] = React.useState(false);
  const aboutText = displayDescription || character.description || "";
  const shouldCollapseAbout = aboutText.length > 420;
  const visibleAbout = shouldCollapseAbout && !aboutExpanded
    ? `${aboutText.slice(0, 400).trim()}...`
    : aboutText;
  const heroBadges = [
    { className: "status", value: formatMetadataValue(character.status, "status") },
    { className: "species", value: formatMetadataValue(character.race_or_species, "race_or_species") },
    { className: "position", value: formatMetadataValue(character.current_position, "current_position") },
    { className: "cultivation", value: currentCultivation },
  ].filter((badge) => badge.value && !isUnknown(badge.value));
  const heroMeta = [
    { Icon: Building2, value: formatMetadataValue(character.faction_or_affiliation, "faction_or_affiliation") },
    { Icon: MapPin, value: formatMetadataValue(character.origin, "origin") },
  ].filter((row) => row.value && !isUnknown(row.value));
  const quickFacts = [
    { Icon: BadgeCheck, label: "Status", value: formatMetadataValue(character.status, "status") },
    { Icon: UserRound, label: "Gender", value: formatMetadataValue(character.gender, "gender") },
    { Icon: Dna, label: "Race / Species", value: formatMetadataValue(character.race_or_species, "race_or_species") },
    { Icon: Building2, label: "Affiliation", value: formatMetadataValue(character.faction_or_affiliation, "faction_or_affiliation") },
    { Icon: MapPin, label: "Origin", value: formatMetadataValue(character.origin, "origin") },
    { Icon: Calendar, label: "Age", value: formatMetadataValue(character.age_text, "age_text") },
    { Icon: BookOpen, label: "First Appeared", value: chapterLabel(character.first_appeared_chapter) },
    { Icon: BookOpen, label: "First Mentioned", value: chapterLabel(character.first_mentioned_chapter) },
    { Icon: Crown, label: "Latest Title", value: formatMetadataValue(latestTitle, "titles") },
  ].filter((fact) => fact.value && !isUnknown(fact.value));

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

  function isUnknown(value) {
    return !value || /^unknown/i.test(String(value).trim());
  }

  function relationshipChapter(relationship) {
    return relationship.chapter ? `Chapter ${relationship.chapter.chapter_number}` : "Unknown chapter";
  }

  function evidenceChapterBadge(row) {
    return row.chapter?.chapter_number ? `Ch. ${row.chapter.chapter_number}` : "Ch. ?";
  }

  return (
    <article className="wiki-character-page">
      <section className="wiki-character-hero-card">
        <div className="wiki-character-hero-avatar">
          <WikiAvatar name={character.name} />
        </div>

        <div className="wiki-character-hero-main">
          <div className="wiki-title-row">
            <h1>{character.name}</h1>
          </div>

          {heroBadges.length ? (
            <div className="wiki-character-hero-badges">
              {heroBadges.map((badge) => (
                <span className={badge.className} key={`${badge.className}-${badge.value}`}>{badge.value}</span>
              ))}
            </div>
          ) : null}

          {heroMeta.length ? (
            <div className="wiki-character-hero-meta">
              {heroMeta.map(({ Icon, value }) => (
                <span key={value}>
                  <Icon aria-hidden="true" size={15} strokeWidth={2} />
                  {value}
                </span>
              ))}
            </div>
          ) : null}

          {displayDescription ? <p className="wiki-character-hero-description">{displayDescription}</p> : null}

          <div className="wiki-character-hero-stats">
            <span>
              <Sparkles aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{skills.length}</strong>
              <small>Skills</small>
            </span>
            <span>
              <Package aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{items.length}</strong>
              <small>Items</small>
            </span>
            <span>
              <Zap aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{cultivationEvents.length}</strong>
              <small>Breakthroughs</small>
            </span>
            <span>
              <BookOpen aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{evidence.length}</strong>
              <small>Evidence</small>
            </span>
          </div>
        </div>
      </section>

      <section className="wiki-character-profile-grid">
        <div className="wiki-character-profile-main-column">
          <section className="wiki-card wiki-current-cultivation-card">
            <span className="wiki-current-cultivation-icon">
              <Activity aria-hidden="true" size={24} strokeWidth={2} />
            </span>
            <div>
              <h2>Current Cultivation</h2>
              <strong>{currentCultivation || "No cultivation recorded"}</strong>
              {currentCultivationEvent?.chapter ? (
                <p>
                  Confirmed in Chapter {currentCultivationEvent.chapter.chapter_number}
                  {cleanChapterTitle(currentCultivationEvent.chapter)
                    ? <span>{cleanChapterTitle(currentCultivationEvent.chapter)}</span>
                    : null}
                </p>
              ) : (
                <p>Full progression history is available on the cultivation timeline.</p>
              )}
              <button className="wiki-outline-link" type="button" onClick={onOpenCultivation}>
                View full progression <span aria-hidden="true">→</span>
              </button>
            </div>
          </section>

          <section className="wiki-card wiki-character-about-card">
            <h2>About</h2>
            <p className="wiki-section-copy">
              {visibleAbout || "No character description has been added yet."}
            </p>
            {shouldCollapseAbout ? (
              <button className="wiki-outline-link" type="button" onClick={() => setAboutExpanded((expanded) => !expanded)}>
                {aboutExpanded ? "View less" : "View more"} <span aria-hidden="true">⌄</span>
              </button>
            ) : null}
          </section>
        </div>

        <section className="wiki-card wiki-quick-facts-card">
          <h2>Quick Facts</h2>
          <div className="wiki-quick-facts-list">
            {quickFacts.map(({ Icon, ...fact }) => (
              <div className="wiki-quick-fact-row" key={fact.label}>
                <span className="wiki-fact-icon">
                  <Icon aria-hidden="true" size={16} strokeWidth={2} />
                </span>
                <small>{fact.label}</small>
                <strong>{fact.value}</strong>
              </div>
            ))}
          </div>
        </section>
      </section>

      {aliases.length ? (
        <section className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Aliases</h2>
            <span>{aliases.length}</span>
          </div>
          <div className="wiki-alias-cloud">
            {aliases.map((alias) => (
              <span key={alias.id}>{alias.alias}</span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="wiki-card wiki-relationships-card">
        <div className="wiki-card-heading">
          <h2>Relationships</h2>
          <button className="wiki-text-link" type="button" disabled>
            View all relationships <span aria-hidden="true">→</span>
          </button>
        </div>
        <p className="wiki-muted-copy">Character relationships are not available yet.</p>
      </section>

      <section className="wiki-character-summary-grid">
        <section className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Skills</h2>
            {skills.length > 0 ? (
              <button className="wiki-text-link" type="button" onClick={onOpenSkills}>
                View all skills <span aria-hidden="true">→</span>
              </button>
            ) : null}
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
                    <p>
                      {relationship.skill?.category ? (
                        <em className={`wiki-type-badge skill ${skillCategoryClass(relationship.skill.category)}`}>
                          {relationship.skill.category}
                        </em>
                      ) : null}
                      <span>{relationshipChapter(relationship)}</span>
                    </p>
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
            <h2>Items</h2>
            {items.length > 0 ? (
              <button className="wiki-text-link" type="button" onClick={onOpenItems}>
                View all items <span aria-hidden="true">→</span>
              </button>
            ) : null}
          </div>
          {shownItems.length > 0 ? (
            <div className="wiki-summary-list">
              {shownItems.map((relationship) => {
                const itemType = relationship.item ? itemTypeFor(relationship.item) : "miscellaneous";

                return (
                  <button
                    className="wiki-summary-row item"
                    disabled={!relationship.item || !onSelectItem}
                    key={relationship.id}
                    type="button"
                    onClick={() => onSelectItem(relationship.item)}
                  >
                    <span className={`wiki-item-type-icon ${itemType}`}>
                      <ItemTypeIcon type={itemType} />
                    </span>
                    <div>
                      <strong>{relationship.item ? relationship.item.name : "Unknown item"}</strong>
                      <p>
                        <em className={`wiki-type-badge ${itemType}`}>{itemTypeLabel(itemType)}</em>
                        <span>{relationshipChapter(relationship)}</span>
                      </p>
                    </div>
                    <span className="wiki-row-action">›</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="wiki-muted-copy">No items recorded yet.</p>
          )}
        </section>
      </section>

      <section className="wiki-card wiki-evidence-list-card">
        <div className="wiki-card-heading">
          <h2>Evidence Highlights</h2>
        </div>
        {shownEvidence.length > 0 ? (
          <div className="wiki-evidence-compact-list">
            {shownEvidence.map((row) => (
              <article className="wiki-evidence-compact-row" key={row.id}>
                <span>{evidenceChapterBadge(row)}</span>
                <p>"{shortEvidence(row.evidence_text)}"</p>
                <span className="wiki-row-action">›</span>
              </article>
            ))}
          </div>
        ) : (
          <p className="wiki-muted-copy">No evidence snippets recorded yet.</p>
        )}
      </section>
    </article>
  );
}
