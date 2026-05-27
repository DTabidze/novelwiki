import React from "react";

export default function ProgressBar({ value = 0 }) {
  const boundedValue = Math.max(0, Math.min(100, Number(value) || 0));

  return (
    <div className="admin-progress">
      <span style={{ width: `${boundedValue}%` }} />
    </div>
  );
}
