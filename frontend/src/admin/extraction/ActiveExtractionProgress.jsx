import React from "react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

export default function ActiveExtractionProgress({ activeRun, isRunningExtraction }) {
  const fallbackRunning = isRunningExtraction && !activeRun;
  const progress = activeRun?.total_chapters
    ? Math.round((activeRun.completed_chapters / activeRun.total_chapters) * 100)
    : 0;

  return (
    <section className="admin-panel extraction-active-panel">
      <div className="admin-section-header">
        <h2>Active Extraction Progress</h2>
        <StatusBadge tone={activeRun ? "info" : "neutral"}>
          {activeRun?.status || (fallbackRunning ? "running" : "idle")}
        </StatusBadge>
      </div>

      {activeRun ? (
        <>
          <h3>
            {activeRun.book ? `Book ${activeRun.book.number}` : "Novel"} · {activeRun.scope_type.replaceAll("_", " ")}
          </h3>
          <strong className="extraction-progress-number">{progress}%</strong>
          <span className="admin-muted">
            {activeRun.completed_chapters} / {activeRun.total_chapters} chapters completed
          </span>
          <ProgressBar value={progress} />
          <div className="extraction-summary-grid">
            <span>Current chapter <strong>{activeRun.current_chapter?.title || "None"}</strong></span>
            <span>Records created <strong>{activeRun.created_records_count}</strong></span>
            <span>Warnings <strong>{activeRun.warning_count}</strong></span>
            <span>Failed chapters <strong>{activeRun.failed_chapters}</strong></span>
          </div>
        </>
      ) : (
        <div className="extraction-idle-state">
          <strong>{fallbackRunning ? "Extraction request is running" : "No active extraction run"}</strong>
          <p className="admin-muted">
            {fallbackRunning
              ? "This MVP processes synchronously, so progress appears when the request completes."
              : "Start a book, range, single chapter, or full novel extraction from the actions panel."}
          </p>
        </div>
      )}
    </section>
  );
}
