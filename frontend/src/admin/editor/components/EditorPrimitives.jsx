import React from "react";
import { CircleAlert } from "lucide-react";

import { formatChapter } from "../editorDrafts.js";

export function EditorField({ label, children, required = false }) {
  return (
    <label className="admin-form-row">
      <span className="admin-form-label">
        {label}
        {required ? <CircleAlert className="editor-required-mark" aria-label="Required" size={15} /> : null}
      </span>
      {children}
    </label>
  );
}

export function RelationList({ rows, emptyMessage, renderTitle, renderMeta }) {
  if (!rows?.length) {
    return <div className="editor-empty-inline">{emptyMessage}</div>;
  }

  return (
    <div className="editor-relation-list">
      {rows.map((row) => (
        <article className="editor-relation-row" key={row.id}>
          <div>
            <strong>{renderTitle(row)}</strong>
            <span>{renderMeta(row)}</span>
          </div>
          <small>{formatChapter(row.chapter)}</small>
        </article>
      ))}
    </div>
  );
}
