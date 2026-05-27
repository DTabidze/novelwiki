import React from "react";
import { ArrowRight, CheckCircle2, CircleAlert, LoaderCircle, MoreHorizontal } from "lucide-react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function relativeActivity(value) {
  if (!value) {
    return "No extraction yet";
  }

  const deltaSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  const days = Math.floor(deltaSeconds / 86400);
  const hours = Math.floor((deltaSeconds % 86400) / 3600);
  const minutes = Math.floor((deltaSeconds % 3600) / 60);

  if (days > 0) return `${days} day${days === 1 ? "" : "s"} ago`;
  if (hours > 0) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  if (minutes > 0) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  return "Just now";
}

function extractionStatusIcon(status) {
  if (status === "completed") return CheckCircle2;
  if (status === "failed") return CircleAlert;
  if (status === "running" || status === "queued") return LoaderCircle;
  return CircleAlert;
}

export default function NovelCard({ novel, onEdit, onOpen }) {
  const chapterCount = novel.chapter_count || 0;
  const extractedCount = novel.extracted_chapter_count || 0;
  const pendingCount = novel.pending_review_count || 0;
  const warningCount = novel.warning_count || 0;
  const approvedCount = novel.approved_record_count || 0;
  const progress = chapterCount ? Math.round((extractedCount / chapterCount) * 100) : 0;
  const lastActivity = novel.last_extraction_at;
  const statusTone = novel.status === "failed"
    ? "danger"
    : novel.status === "draft"
      ? "warning"
      : "success";
  const ExtractionStatusIcon = extractionStatusIcon(novel.last_extraction_status);

  return (
    <article className="admin-novel-card">
      <div className="library-novel-identity">
        {novel.cover_image_url ? (
          <img className="admin-cover-placeholder" src={novel.cover_image_url} alt="" />
        ) : (
          <div className="admin-cover-placeholder">{novel.title?.slice(0, 2) || "NW"}</div>
        )}

        <div className="admin-novel-info">
          <h3 title={novel.title}>{novel.title}</h3>
          <div className="library-title-meta">
            <StatusBadge tone={statusTone}>{novel.status}</StatusBadge>
          </div>
        </div>
      </div>

      <div className="library-review-cell">
        <span>Review Coverage</span>
        <strong>{progress}%</strong>
        <div>
          <ProgressBar value={progress} />
        </div>
        <small>{extractedCount} / {chapterCount} chapters reviewed</small>
      </div>

      <div className="library-count-cell">
        <strong className="admin-good-text">{approvedCount}</strong>
        <span>Approved</span>
      </div>

      <div className="library-count-cell">
        <strong className={pendingCount ? "admin-warning-text" : ""}>{pendingCount}</strong>
        <span>Items</span>
      </div>

      <div className="library-count-cell">
        <strong className={warningCount ? "admin-danger-text" : ""}>{warningCount}</strong>
        <span>{warningCount ? "View all" : "Clear"}</span>
      </div>

      <div className="library-activity-cell">
        <strong>{relativeActivity(lastActivity)}</strong>
        <span className={`library-activity-status ${novel.last_extraction_status || "not-started"}`}>
          <ExtractionStatusIcon aria-hidden="true" size={14} strokeWidth={1.9} />
          {novel.last_extraction_status || "Not started"}
        </span>
      </div>

      <div className="admin-card-actions">
        <button type="button" onClick={() => onOpen(novel)}>
          Workspace
          <ArrowRight aria-hidden="true" size={16} strokeWidth={1.9} />
        </button>
        <button
          className="admin-icon-button"
          type="button"
          aria-label={`Edit ${novel.title}`}
          onClick={() => onEdit(novel)}
        >
          <MoreHorizontal aria-hidden="true" size={17} strokeWidth={1.9} />
        </button>
      </div>
    </article>
  );
}
