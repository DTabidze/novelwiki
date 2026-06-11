import React from "react";
import { BookOpen, FileText, Users } from "lucide-react";
import WikiAvatar from "./WikiAvatar.jsx";
import { ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemsIndex.jsx";
import { chapterLabel, initialsForName } from "../../utils/wikiFormat.js";

function compactEvidence(text, limit = 150) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();

  if (normalized.length <= limit) {
    return normalized;
  }

  return `${normalized.slice(0, limit - 3).trim()}...`;
}

function chapterNumber(chapter) {
  return Number(chapter?.chapter_number) || Number.MAX_SAFE_INTEGER;
}

function chapterBadge(chapter) {
  return chapter?.chapter_number ? `Ch. ${chapter.chapter_number}` : "Ch. ?";
}

function firstChapter(...rows) {
  return rows
    .flat()
    .map((row) => row?.chapter)
    .filter(Boolean)
    .sort((first, second) => chapterNumber(first) - chapterNumber(second))[0];
}

function relationshipTypeLabel(type) {
  const normalized = String(type || "").replace(/_/g, " ").trim();

  if (!normalized) {
    return "";
  }

  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export default function WikiItemPage({ item, onSelectCharacter }) {
  const [showAllTimeline, setShowAllTimeline] = React.useState(false);

  if (!item) {
    return (
      <section className="wiki-empty-panel">
        <h2>Loading item</h2>
        <p>The item page will appear once the approved wiki data loads.</p>
      </section>
    );
  }

  const relatedCharacters = (item.characters || []).filter(
    (relationship) => relationship.character || relationship.character_name
  );
  const evidence = item.evidence || [];
  const itemType = itemTypeFor(item);
  const firstSeenChapter = firstChapter(relatedCharacters, evidence);
  const timelineRows = [
    ...relatedCharacters.map((relationship) => ({
      id: `relationship-${relationship.id}`,
      chapter: relationship.chapter,
      summary: relationship.description || `${relationship.character?.name || relationship.character_name} is linked to ${item.name}.`,
      evidence: relationship.evidence?.[0]?.evidence_text || "",
    })),
    ...evidence.map((row) => ({
      id: `evidence-${row.id}`,
      chapter: row.chapter,
      summary: `${item.name} is mentioned in the source text.`,
      evidence: row.evidence_text,
    })),
  ]
    .filter((row) => row.chapter || row.summary || row.evidence)
    .sort((first, second) => chapterNumber(first.chapter) - chapterNumber(second.chapter));
  const visibleTimelineRows = showAllTimeline ? timelineRows : timelineRows.slice(0, 4);

  return (
    <article className="wiki-skill-detail-page wiki-item-detail-page">
      <section className="wiki-skill-hero-card wiki-item-hero-card">
        <div className="wiki-skill-hero-art wiki-item-hero-art">
          <div className="wiki-skill-hero-avatar">
            <span>{initialsForName(item.name)}</span>
          </div>
        </div>

        <div className="wiki-skill-hero-main">
          <h1>{item.name}</h1>
          {item.category ? (
            <span className={`wiki-type-badge ${itemType}`}>
              <ItemTypeIcon type={itemType} />
              {item.category || itemTypeLabel(itemType)}
            </span>
          ) : null}
          {item.description ? <p>{item.description}</p> : null}

          <div className="wiki-skill-stat-grid">
            <span>
              <Users aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{relatedCharacters.length}</strong>
              <small>{relatedCharacters.length === 1 ? "Character" : "Characters"}</small>
            </span>
            {evidence.length ? (
              <span>
                <FileText aria-hidden="true" size={18} strokeWidth={2} />
                <strong>{evidence.length}</strong>
                <small>Evidence Records</small>
              </span>
            ) : null}
            {firstSeenChapter ? (
              <span>
                <BookOpen aria-hidden="true" size={18} strokeWidth={2} />
                <strong>Chapter {firstSeenChapter.chapter_number}</strong>
                <small>First Seen</small>
              </span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="wiki-card wiki-skill-section-card">
        <div className="wiki-card-heading">
          <h2>Known Owners & Users</h2>
          {relatedCharacters.length ? (
            <button className="wiki-text-link" type="button">
              View all characters <span aria-hidden="true">→</span>
            </button>
          ) : null}
        </div>

        {relatedCharacters.length ? (
          <div className="wiki-skill-known-users">
            {relatedCharacters.map((relationship) => {
              const character = relationship.character;
              const characterName = character?.name || relationship.character_name || "Unknown character";
              const chapter = chapterLabel(relationship.chapter);
              const typeLabel = relationshipTypeLabel(relationship.relationship_type);

              return (
                <button
                  className="wiki-skill-known-user-row wiki-item-owner-row"
                  disabled={!character}
                  key={relationship.id}
                  type="button"
                  onClick={() => character && onSelectCharacter(character)}
                >
                  <WikiAvatar name={characterName} size="small" />
                  <span>
                    <strong>{characterName}</strong>
                    {relationship.description ? <small>{relationship.description}</small> : null}
                  </span>
                  <span className="wiki-skill-row-chapter" title={chapter}>
                    {chapter}
                    {typeLabel ? <small>{typeLabel}</small> : null}
                  </span>
                  <span className="wiki-row-action">›</span>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="wiki-muted-copy">No approved related characters yet.</p>
        )}
      </section>

      <section className="wiki-card wiki-skill-section-card">
        <div className="wiki-card-heading">
          <h2>Item Timeline</h2>
          {timelineRows.length ? (
            <button className="wiki-text-link" type="button">
              View full timeline <span aria-hidden="true">→</span>
            </button>
          ) : null}
        </div>

        {visibleTimelineRows.length ? (
          <div className="wiki-skill-timeline">
            {visibleTimelineRows.map((row) => (
              <article className="wiki-skill-timeline-row" key={row.id}>
                <span className="wiki-skill-timeline-dot" />
                <div>
                  <small>{chapterLabel(row.chapter)}</small>
                  {row.summary ? <strong>{row.summary}</strong> : null}
                  {row.evidence ? <p>"{compactEvidence(row.evidence)}"</p> : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="wiki-muted-copy">No item timeline records yet.</p>
        )}

        {timelineRows.length > 4 ? (
          <button
            className="wiki-outline-link wiki-skill-timeline-toggle"
            type="button"
            onClick={() => setShowAllTimeline((visible) => !visible)}
          >
            {showAllTimeline ? "Show fewer timeline records" : `View all ${timelineRows.length} timeline records`}
            <span aria-hidden="true">⌄</span>
          </button>
        ) : null}
      </section>

      <section className="wiki-card wiki-evidence-list-card">
        <div className="wiki-card-heading">
          <h2>Evidence Highlights</h2>
          {evidence.length ? (
            <button className="wiki-text-link" type="button">
              View all evidence <span aria-hidden="true">→</span>
            </button>
          ) : null}
        </div>

        {evidence.length ? (
          <div className="wiki-evidence-compact-list">
            {evidence.slice(0, 5).map((row) => (
              <article className="wiki-evidence-compact-row" key={row.id}>
                <span>{chapterBadge(row.chapter)}</span>
                <p>"{compactEvidence(row.evidence_text)}"</p>
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
