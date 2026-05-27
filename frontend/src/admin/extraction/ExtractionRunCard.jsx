import React from "react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatRunDate, runProgress, runTitle, statusTone } from "./extractionUtils.js";

export default function ExtractionRunCard({ run }) {
  const progress = runProgress(run);

  return (
    <article className={`extraction-run-card ${run.status}`}>
      <div className="extraction-run-icon">{run.status.slice(0, 1).toUpperCase()}</div>
      <div className="extraction-run-main">
        <strong>{runTitle(run)}</strong>
        <span>{run.started_at ? `Started ${formatRunDate(run.started_at)}` : "Queued"}</span>
        {run.error_message ? <small className="admin-danger-text">{run.error_message}</small> : null}
      </div>
      <div className="extraction-run-progress">
        <StatusBadge tone={statusTone(run.status)}>{run.status}</StatusBadge>
        <ProgressBar value={progress} />
        <span>{run.completed_chapters} / {run.total_chapters} chapters</span>
      </div>
      <div className="extraction-run-counts">
        <span>{run.created_records_count} records</span>
        <span>{run.warning_count} warnings</span>
      </div>
    </article>
  );
}
