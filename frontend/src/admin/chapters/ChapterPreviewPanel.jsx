import React from "react";

export default function ChapterPreviewPanel({ chapter, onExtract, onReview, extractingChapterId }) {
  if (!chapter) {
    return (
      <section className="admin-panel chapter-preview-panel">
        <h2>Chapter Preview</h2>
        <p className="admin-muted">Select a chapter to inspect its parsed metadata and preview.</p>
      </section>
    );
  }

  const isExtracting = extractingChapterId === chapter.id;

  return (
    <section className="admin-panel chapter-preview-panel">
      <div className="admin-section-header">
        <div>
          <h2>{chapter.title}</h2>
          <span>
            Book {chapter.book?.number || "?"} · Chapter {chapter.chapter_number}
          </span>
        </div>
      </div>

      <div className="chapter-preview-meta">
        <span>Characters: <strong>{chapter.character_count?.toLocaleString() || 0}</strong></span>
        <span>Pending: <strong>{chapter.pending_review_count || 0}</strong></span>
        <span>Warnings: <strong>{chapter.warning_count || 0}</strong></span>
      </div>

      <div className="chapter-preview-text">
        <p>{chapter.preview}</p>
      </div>

      <div className="chapter-preview-actions">
        <button disabled={isExtracting} type="button" onClick={() => onExtract(chapter)}>
          {isExtracting ? "Extracting..." : "Extract Chapter"}
        </button>
        <button className="admin-secondary-button" type="button" onClick={() => onReview(chapter)}>
          Review Chapter
        </button>
      </div>
    </section>
  );
}
