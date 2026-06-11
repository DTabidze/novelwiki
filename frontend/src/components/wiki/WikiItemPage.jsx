import React from "react";
import { BookOpen, Users } from "lucide-react";
import WikiAvatar from "./WikiAvatar.jsx";
import { WikiEvidence } from "./WikiDetailPages.jsx";
import { ItemTypeIcon, itemTypeFor } from "./WikiItemsIndex.jsx";
import { chapterLabel, relationshipLabel } from "../../utils/wikiFormat.js";

export default function WikiItemPage({ item, onSelectCharacter }) {
  if (!item) {
    return (
      <section className="wiki-empty-panel">
        <h2>Loading item</h2>
        <p>The item page will appear once the approved wiki data loads.</p>
      </section>
    );
  }

  const relatedCharacters = (item.characters || []).filter((relationship) => relationship.character);
  const itemType = itemTypeFor(item);

  return (
    <article className="wiki-entity-page">
      <section className="wiki-entity-hero item">
        <div className="wiki-entity-art">
          <WikiAvatar name={item.name} />
        </div>
        <div className="wiki-entity-main">
          <div className="wiki-title-row">
            <h1>{item.name}</h1>
          </div>

          <div className="wiki-fact-grid">
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <ItemTypeIcon type={itemType} />
              </span>
              <div>
                <small>Item Type</small>
                <strong>{item.category || "Item"}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <Users aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>Related Characters</small>
                <strong>{relatedCharacters.length}</strong>
              </div>
            </div>
            <div className="wiki-fact">
              <span className="wiki-fact-icon">
                <BookOpen aria-hidden="true" size={16} strokeWidth={2} />
              </span>
              <div>
                <small>First Evidence</small>
                <strong>{chapterLabel(item.evidence?.[0]?.chapter)}</strong>
              </div>
            </div>
          </div>

          {item.description ? <p className="wiki-description">{item.description}</p> : null}
        </div>
      </section>

      <section className="wiki-content-grid">
        <div className="wiki-card wiki-progression-card">
          <h2>History & Evidence</h2>
          <WikiEvidence evidence={item.evidence} />
          {relatedCharacters.length > 0 ? (
            <div className="wiki-usage-list">
              {relatedCharacters.map((relationship) => (
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
            <h2>Related Characters</h2>
            {relatedCharacters.length === 0 ? <p>No approved related characters yet.</p> : null}
            {relatedCharacters.map((relationship) => (
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

        </div>
      </section>
    </article>
  );
}
