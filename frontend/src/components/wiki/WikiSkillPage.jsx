import React from "react";
import { BookOpen, FileText, Tags, Users } from "lucide-react";
import WikiBookmarkButton from "./WikiBookmarkButton.jsx";
import WikiAvatar from "./WikiAvatar.jsx";
import { WikiDetailSkeleton } from "./WikiSkeletons.jsx";
import {
  chapterBadge,
  chapterLabel,
  chapterNumberValue,
  compactEvidence,
  firstChapterFromRows,
  initialsForName,
  relationshipLabel,
  skillCategoryClass,
} from "../../utils/wikiFormat.js";

export default function WikiSkillPage({ isLoading = false, onSelectCharacter, onToggleBookmark, skill }) {
  const [showAllTimeline, setShowAllTimeline] = React.useState(false);

  if (isLoading) {
    return <WikiDetailSkeleton variant="skill" />;
  }

  if (!skill) {
    return (
      <section className="wiki-empty-panel">
        <h2>Select a skill</h2>
        <p>Choose an approved skill to view its public wiki page.</p>
      </section>
    );
  }

  const knownUsers = (skill.characters || []).filter((relationship) => relationship.character);
  const aliases = skill.aliases || [];
  const evidence = skill.evidence || [];
  const firstSeenChapter = firstChapterFromRows(knownUsers, aliases, evidence);
  const timelineRows = [
    ...knownUsers.map((relationship) => ({
      id: `relationship-${relationship.id}`,
      chapter: relationship.chapter,
      summary: relationship.description || relationshipLabel(relationship),
      evidence: relationship.evidence?.[0]?.evidence_text || "",
    })),
    ...evidence.map((row) => ({
      id: `evidence-${row.id}`,
      chapter: row.chapter,
      summary: `${skill.name} is mentioned in the source text.`,
      evidence: row.evidence_text,
    })),
  ]
    .filter((row) => row.chapter || row.summary || row.evidence)
    .sort((first, second) => chapterNumberValue(first.chapter) - chapterNumberValue(second.chapter));
  const visibleTimelineRows = showAllTimeline ? timelineRows : timelineRows.slice(0, 4);
  const skillBadgeClass = `wiki-type-badge skill ${skillCategoryClass(skill.category)}`;

  return (
    <article className="wiki-skill-detail-page">
      <section className="wiki-character-hero-card wiki-entity-detail-hero-card skill">
        <div className="wiki-character-hero-avatar wiki-entity-detail-hero-avatar">
          <div className="wiki-skill-hero-avatar">
            <span>{initialsForName(skill.name)}</span>
          </div>
        </div>

        <div className="wiki-character-hero-main">
          <div className="wiki-title-row">
            <h1>{skill.name}</h1>
            <WikiBookmarkButton entity={skill} entityType="skill" onToggle={onToggleBookmark} />
          </div>
          {skill.category ? (
            <div className="wiki-character-hero-badges">
              <span className={skillBadgeClass}>{skill.category}</span>
            </div>
          ) : null}
          {skill.description ? <p className="wiki-character-hero-description">{skill.description}</p> : null}

          <div className="wiki-character-hero-stats">
            <span>
              <Users aria-hidden="true" size={18} strokeWidth={2} />
              <strong>{knownUsers.length}</strong>
              <small>Known Users</small>
            </span>
            {aliases.length ? (
              <span>
                <Tags aria-hidden="true" size={18} strokeWidth={2} />
                <strong>{aliases.length}</strong>
                <small>Aliases</small>
              </span>
            ) : null}
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
          <h2>Known Users</h2>
          {knownUsers.length ? (
            <button className="wiki-text-link" type="button">
              View all users <span aria-hidden="true">→</span>
            </button>
          ) : null}
        </div>

        {knownUsers.length ? (
          <div className="wiki-skill-known-users">
            {knownUsers.map((relationship) => {
              const chapter = chapterLabel(relationship.chapter);

              return (
                <button
                  className="wiki-skill-known-user-row wiki-item-owner-row"
                  key={relationship.id}
                  type="button"
                  onClick={() => onSelectCharacter(relationship.character)}
                >
                  <WikiAvatar name={relationship.character.name} size="small" />
                  <span>
                    <strong>{relationship.character.name}</strong>
                  </span>
                  <span className="wiki-skill-row-chapter" title={chapter}>{chapter}</span>
                  <span className="wiki-row-action">›</span>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="wiki-muted-copy">No approved known users yet.</p>
        )}
      </section>

      {aliases.length ? (
        <section className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Aliases</h2>
          </div>

          <div className="wiki-alias-cloud">
            {aliases.map((alias) => (
              <span key={alias.id}>{alias.alias}</span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="wiki-card wiki-skill-section-card">
        <div className="wiki-card-heading">
          <h2>Usage Timeline</h2>
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
          <p className="wiki-muted-copy">No usage timeline records yet.</p>
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
