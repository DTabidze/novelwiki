import React from "react";

export default function StatusBadge({ tone = "neutral", children }) {
  return <span className={`admin-status-badge ${tone}`}>{children || "Unknown"}</span>;
}
