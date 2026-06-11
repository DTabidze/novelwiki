import React from "react";
import { BookOpen, Sparkles, Tags, Users } from "lucide-react";
import WikiAvatar from "./WikiAvatar.jsx";
import { WikiEvidence } from "./WikiDetailPages.jsx";
import { chapterLabel, relationshipLabel } from "../../utils/wikiFormat.js";

export default function WikiSkillPage({ onSelectCharacter, skill }) {
  if (!skill) {
    return (
      <section className="wiki-empty-panel">
        <h2>Loading skill</h2>
        <p>The skill page will appear once the approved wiki data loads.</p>
      </section>
    );
  }

  const knownUsers = (skill.characters || []).filter((relationship) => relationship.character);

  return (
    <article className="wiki-entity-page">
      <section className="wiki-entity-hero skill">
        <div className="wiki-entity-art">
          <WikiAvatar name={skill.name} />
        </div>
        <div className="wiki-entity-main">
          <div className="wiki-title-row">
            <h1>{skill.name}</h1>
          </div>

          <div className="wiki-fact-grid">
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <Sparkles aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>Skill Type</small>
                <strong>{skill.category || "Technique"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <Users aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>Known Users</small>
                <strong>{knownUsers.length}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <BookOpen aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>First Evidence</small>
                <strong>{chapterLabel(skill.evidence?.[0]?.chapter)}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <Tags aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>Aliases</small>
                <strong>
                  {skill.aliases && skill.aliases.length > 0
                    ? skill.aliases.map((alias) => alias.alias).join(", ")
                    : "N/A"}
                </strong>
              </div>
            </div>
          </div>

          {skill.description ? <p className="wiki-description">{skill.description}</p> : null}
        </div>
      </section>

      <section className="wiki-content-grid">
        <div className="wiki-card wiki-progression-card">
          <h2>Evidence & Usage</h2>
          <WikiEvidence evidence={skill.evidence} />
          {knownUsers.length > 0 ? (
            <div className="wiki-usage-list">
              {knownUsers.map((relationship) => (
                <article className="wiki-usage-row" key={relationship.id}>
                  <span className="wiki-timeline-dot" />
                  <div>
                    <small>{chapterLabel(relationship.chapter)}</small>
                    <strong>{relationshipLabel(relationship)}</strong>
                    {relationship.description ? <p>{relationship.description}</p> : null}
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </div>

        <div className="wiki-side-stack">
          <section className="wiki-card">
            <h2>Known Users</h2>
            {knownUsers.length === 0 ? <p>No approved known users yet.</p> : null}
            {knownUsers.map((relationship) => {
              const chapter = chapterLabel(relationship.chapter);

              return (
                <button
                  className="wiki-related-row"
                  key={relationship.id}
                  type="button"
                  onClick={() => onSelectCharacter(relationship.character)}
                >
                  <WikiAvatar name={relationship.character.name} size="small" />
                  <span>{relationship.character.name}</span>
                  <small title={chapter}>{chapter}</small>
                  <span className="wiki-row-action">›</span>
                </button>
              );
            })}
          </section>
        </div>
      </section>
    </article>
  );
}
