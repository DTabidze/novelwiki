import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import { WikiEvidence } from "./WikiDetailPages.jsx";
import { chapterLabel, relationshipLabel } from "../../utils/wikiFormat.js";

export default function WikiSkillPage({ onSelectCharacter, relatedSkills = [], skill }) {
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
            <span className="wiki-title-mark">Art</span>
          </div>

          <div className="wiki-fact-grid">
            <div className="wiki-fact">
              <span className="wiki-fact-icon">T</span>
              <div>
                <small>Skill Type</small>
                <strong>{skill.category || "Technique"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">U</span>
              <div>
                <small>Known Users</small>
                <strong>{knownUsers.length}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">B</span>
              <div>
                <small>First Evidence</small>
                <strong>{chapterLabel(skill.evidence?.[0]?.chapter)}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">A</span>
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
            {knownUsers.map((relationship) => (
              <button
                className="wiki-related-row"
                key={relationship.id}
                type="button"
                onClick={() => onSelectCharacter(relationship.character)}
              >
                <WikiAvatar name={relationship.character.name} size="small" />
                <span>{relationship.character.name}</span>
                <small>{relationshipLabel(relationship)}</small>
              </button>
            ))}
          </section>

          <section className="wiki-card">
            <h2>Related Skills</h2>
            {relatedSkills.length === 0 ? <p>No related skills yet.</p> : null}
            {relatedSkills
              .filter((related) => related.id !== skill.id)
              .slice(0, 3)
              .map((related) => (
                <div className="wiki-mini-link" key={related.id}>
                  <strong>{related.name}</strong>
                  <span>{related.category || "Skill"}</span>
                </div>
              ))}
          </section>
        </div>
      </section>
    </article>
  );
}
