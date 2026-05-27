import React from "react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function NovelCard({ novel, onOpen }) {
  const bookCount = novel.book_count || 0;
  const chapterCount = novel.chapter_count || 0;
  const extractedCount = novel.extracted_chapter_count || 0;
  const pendingCount = novel.pending_review_count || 0;
  const warningCount = novel.warning_count || 0;
  const progress = chapterCount ? Math.round((extractedCount / chapterCount) * 100) : 0;

  return (
    <article className="admin-novel-card">
      <div className="admin-cover-placeholder">{novel.title?.slice(0, 2) || "NW"}</div>

      <div className="admin-novel-info">
        <h3>{novel.title}</h3>
        <p>{novel.description || "Novel workspace for reviewed extraction data."}</p>
        <div className="admin-card-meta">
          <StatusBadge tone={novel.status === "failed" ? "danger" : "success"}>{novel.status}</StatusBadge>
          <span>Updated {formatDate(novel.updated_at)}</span>
        </div>
      </div>

      <div className="admin-novel-metrics">
        <div>
          <span>Books</span>
          <strong>{bookCount}</strong>
        </div>
        <div>
          <span>Chapters</span>
          <strong>{chapterCount}</strong>
        </div>
        <div>
          <span>Extracted</span>
          <strong className="admin-good-text">{extractedCount}</strong>
        </div>
        <div>
          <span>Pending</span>
          <strong className={pendingCount ? "admin-warning-text" : ""}>{pendingCount}</strong>
        </div>
        <div>
          <span>Warnings</span>
          <strong className={warningCount ? "admin-danger-text" : ""}>{warningCount}</strong>
        </div>
        <div className="admin-progress-cell">
          <span>Extraction Progress</span>
          <ProgressBar value={progress} />
          <small>{progress}%</small>
        </div>
      </div>

      <div className="admin-card-actions">
        <button type="button" onClick={() => onOpen(novel)}>
          Open Workspace
        </button>
      </div>
    </article>
  );
}
