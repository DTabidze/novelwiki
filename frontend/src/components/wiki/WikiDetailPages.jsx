import React from "react";
export function WikiEvidence({ evidence }) {
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

export function WikiSkillDetail({ skill }) {
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

export function WikiItemDetail({ item }) {
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
