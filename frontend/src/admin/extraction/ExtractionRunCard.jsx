import React from "react";
import { MoreHorizontal } from "lucide-react";
import { runProgress, runTitle } from "./extractionUtils.js";

function relativeRunTime(value) {
  if (!value) {
    return "Queued";
  }

  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return "Just now";
}

function compactRunTitle(run) {
  return runTitle(run).replace(": ", " · ");
}

export default function ExtractionRunCard({ run }) {
  const progress = runProgress(run);
  const warningCount = run.warning_count || 0;

  return (
    <article className={`extraction-run-card ${run.status}`}>
      <div className="extraction-run-header">
        <strong title={runTitle(run)}>{compactRunTitle(run)}</strong>
        <span>{relativeRunTime(run.finished_at || run.started_at || run.created_at)}</span>
        <button className="admin-icon-button extraction-run-menu" type="button" aria-label="Extraction run actions">
          <MoreHorizontal aria-hidden="true" size={16} strokeWidth={1.9} />
        </button>
      </div>

      <div className="extraction-run-meta">
        <b>{run.status}</b>
        <span>{run.completed_chapters}/{run.total_chapters} chapters</span>
        <span>{run.created_records_count} records</span>
        <span className={warningCount > 0 ? "has-warnings" : ""}>{warningCount} warnings</span>
      </div>

      {run.error_message ? <small className="admin-danger-text extraction-run-error">{run.error_message}</small> : null}

      <div className="extraction-run-bar" aria-label={`${progress}% complete`}>
        <span style={{ width: `${progress}%` }} />
      </div>
    </article>
  );
}
