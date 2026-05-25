import React from "react";

export default function EmptyState({ title, message, action }) {
  return (
    <div className="admin-empty-state">
      <h3>{title}</h3>
      {message ? <p>{message}</p> : null}
      {action}
    </div>
  );
}
