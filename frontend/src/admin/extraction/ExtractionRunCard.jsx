import React from "react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function statusTone(status) {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "info";
  return "neutral";
}

function runTitle(run) {
  const bookLabel = run.book ? `Book ${run.book.number}` : "Novel";

  if (run.scope_type === "single_chapter") {
    return `${bookLabel}: Chapter ${run.chapter_start}`;
  }

  if (run.scope_type === "chapter_range") {
    return `${bookLabel}: Chapters ${run.chapter_start}-${run.chapter_end}`;
  }

  if (run.scope_type === "book") {
    return `${bookLabel}: Full Book Extraction`;
  }

  if (run.scope_type === "retry_failed") {
    return "Retry Failed Chapters";
  }

  return "Full Novel Extraction";
}

export default function ExtractionRunCard({ run }) {
  const progress = run.total_chapters
    ? Math.round((run.completed_chapters / run.total_chapters) * 100)
    : 0;

  return (
    <article className="extraction-run-card">
      <div>
        <strong>{runTitle(run)}</strong>
        <span>
          {run.started_at ? `Started ${new Date(run.started_at).toLocaleString()}` : "Queued"}
        </span>
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
