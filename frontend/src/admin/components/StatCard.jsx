import React from "react";

export default function StatCard({ label, value, detail, tone = "blue" }) {
  return (
    <article className="admin-stat-card">
      <div className={`admin-stat-icon ${tone}`}>{label.slice(0, 1)}</div>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
        {detail ? <small>{detail}</small> : null}
      </div>
    </article>
  );
}
