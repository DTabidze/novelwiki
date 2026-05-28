import React from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  Pencil,
  SkipForward,
  X,
} from "lucide-react";
import {
  confidenceLevel,
  confidenceText,
  evidenceRows,
  formatReviewType,
  isAssumedSpeciesOverride,
  proposedDataRows,
  recordSummary,
  reviewTitle,
  reviewWarnings,
  sourceChapter,
} from "./reviewUtils.js";

export default function ReviewDetailPanel({
  item,
  isSaving,
  onApprove,
  onReject,
  onSkip,
  onClose,
  onNext,
  onPrevious,
}) {
  if (!item) {
    return (
      <aside className="review-detail-panel admin-panel">
        <div className="review-detail-empty">
          <strong>Select a review item</strong>
          <p>Choose an extracted record from the queue to inspect evidence and moderate it.</p>
        </div>
      </aside>
    );
  }

  const chapter = sourceChapter(item);
  const rows = proposedDataRows(item);
  const evidence = evidenceRows(item);
  const warnings = reviewWarnings(item);
  const level = confidenceLevel(item);

  return (
    <aside className="review-detail-panel admin-panel">
      <header className="review-detail-header">
        <div>
          <span>Review Item</span>
          <strong>{formatReviewType(item.entityType)}</strong>
        </div>
        <div className="review-detail-tools">
          <button type="button" className="admin-icon-button" onClick={onPrevious} aria-label="Previous item">
            <ChevronLeft size={16} />
          </button>
          <button type="button" className="admin-icon-button" onClick={onNext} aria-label="Next item">
            <ChevronRight size={16} />
          </button>
          <button type="button" className="admin-icon-button" onClick={onClose} aria-label="Close inspector">
            <X size={16} />
          </button>
        </div>
      </header>

      <div className="review-detail-scroll">
        <section className="review-detail-intro">
          <div className="review-detail-kicker">
            <span>{formatReviewType(item.entityType)}</span>
            {chapter ? <small>Chapter {chapter.chapter_number}</small> : null}
          </div>
          <h2>{reviewTitle(item)}</h2>
          <p>
            Confidence: <i className={`review-confidence-dot ${level}`} /> {confidenceText(item)}
          </p>
          {isAssumedSpeciesOverride(item) ? (
            <div className="review-assumption-note">
              This is overriding an assumed default species, not replacing confirmed extracted metadata.
            </div>
          ) : null}
        </section>

        <section className="review-detail-section">
          <h3>Proposed Data</h3>
          <div className="review-data-table">
            {rows.length === 0 ? (
              <p className="admin-muted">No structured fields available for this item.</p>
            ) : (
              rows.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))
            )}
          </div>
        </section>

        {warnings.length > 0 ? (
          <section className="review-detail-section">
            <h3>Warnings</h3>
            <div className="review-warning-box">
              {warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          </section>
        ) : null}

        <section className="review-detail-section">
          <h3>Evidence (from source)</h3>
          {evidence.length === 0 ? (
            <p className="admin-muted">No evidence snippet was attached to this item.</p>
          ) : (
            evidence.slice(0, 3).map((row) => (
              <blockquote className="review-evidence-card" key={row.id || row.evidence_text}>
                <p>{row.evidence_text}</p>
                <footer>
                  <span>{chapter ? `Chapter ${chapter.chapter_number}` : "Source chapter"}</span>
                  <button type="button" className="admin-secondary-button">
                    <Eye size={15} /> View Full Context
                  </button>
                </footer>
              </blockquote>
            ))
          )}
        </section>

        <section className="review-detail-section">
          <h3>AI Notes</h3>
          <p className="review-ai-notes">{item.extraction_reason || recordSummary(item)}</p>
        </section>
      </div>

      <footer className="review-action-footer">
        <strong>Actions</strong>
        <div className="review-action-grid">
          <button type="button" className="review-approve-button" disabled={isSaving} onClick={() => onApprove(item)}>
            <Check size={17} /> Approve
          </button>
          <button type="button" className="review-reject-button" disabled={isSaving} onClick={() => onReject(item)}>
            <X size={17} /> Reject
          </button>
          <button type="button" className="admin-secondary-button" disabled={isSaving}>
            <Pencil size={16} /> Edit
          </button>
          <button type="button" className="admin-secondary-button review-skip-button" disabled={isSaving} onClick={onSkip}>
            <SkipForward size={16} /> Skip for Now
          </button>
        </div>
      </footer>
    </aside>
  );
}
