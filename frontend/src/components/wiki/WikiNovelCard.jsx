import React from "react";
import { BadgeCheck, BookOpen, ChevronRight, Sprout } from "lucide-react";
import WikiBookmarkButton from "./WikiBookmarkButton.jsx";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatNumber } from "../../utils/wikiFormat.js";

export function publicNovelStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();

  if (["ongoing", "tracking", "in_progress"].includes(normalized)) return "Ongoing";
  if (normalized === "hiatus") return "Hiatus";
  if (["complete", "completed", "ready"].includes(normalized)) return "Completed";

  return "Available";
}

function coverageCount(novel) {
  return novel.wiki_coverage_end_chapter || 0;
}

export default function WikiNovelCard({ novel, onOpen, onToggleBookmark }) {
  const statusLabel = publicNovelStatusLabel(novel.status);
  const totalChapters = novel.chapter_count || 0;

  return (
    <article className="wiki-novel-card">
      <WikiBookmarkButton entity={novel} entityType="novel" onToggle={onToggleBookmark} />

      <div className="wiki-novel-card-cover">
        {novel.cover_image_url ? (
          <img src={novel.cover_image_url} alt="" />
        ) : (
          <div className="wiki-novel-cover-placeholder">
            <WikiAvatar name={novel.title} size="large" />
          </div>
        )}
      </div>

      <div className="wiki-novel-card-content">
        <div className="wiki-novel-card-heading">
          <strong>{novel.title}</strong>
          <small>{novel.author || "Unknown author"}</small>
        </div>

        <div className="wiki-novel-card-badges">
          <span className={`wiki-novel-status-pill ${statusLabel.toLowerCase()}`}>
            <BadgeCheck aria-hidden="true" size={17} strokeWidth={2.2} />
            {statusLabel}
          </span>
          <span className="wiki-novel-genre-pill">
            <Sprout aria-hidden="true" size={17} strokeWidth={2.1} />
            Cultivation Novel
          </span>
        </div>

        <div className="wiki-novel-card-divider" />

        <div className="wiki-novel-coverage-panel">
          <span>
            <BookOpen aria-hidden="true" size={22} strokeWidth={2} />
            Wiki Coverage
          </span>
          <strong className="wiki-novel-coverage-value">
            {formatNumber(coverageCount(novel))} / {formatNumber(totalChapters)}
          </strong>
          <small>Chapters</small>
        </div>

        <div className="wiki-novel-card-divider" />
      </div>

      <button className="wiki-novel-card-cta" type="button" onClick={() => onOpen(novel.id)}>
        <BookOpen aria-hidden="true" size={22} strokeWidth={2.1} />
        Browse Wiki
        <ChevronRight aria-hidden="true" size={24} strokeWidth={2.4} />
      </button>
    </article>
  );
}
