import React from "react";
import ActiveExtractionProgress from "./ActiveExtractionProgress.jsx";
import ExtractionRunCard from "./ExtractionRunCard.jsx";
import NewExtractionModal from "./NewExtractionModal.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import StatCard from "../components/StatCard.jsx";

function latestRunWithStatus(runs, status) {
  return runs.find((run) => run.status === status) || null;
}

function countRuns(runs, status) {
  return runs.filter((run) => run.status === status).length;
}

export default function ExtractionPage({
  books,
  chapters,
  extractionRuns,
  isRunningExtraction,
  novel,
  onStartExtraction,
}) {
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const activeRun = latestRunWithStatus(extractionRuns, "running");
  const completedRuns = countRuns(extractionRuns, "completed");
  const failedRuns = countRuns(extractionRuns, "failed");
  const queuedRuns = countRuns(extractionRuns, "queued");
  const extractedChapterCount = extractionRuns
    .filter((run) => run.status === "completed")
    .reduce((sum, run) => sum + (run.completed_chapters || 0), 0);
  const progress = novel?.chapter_count
    ? Math.round((Math.min(extractedChapterCount, novel.chapter_count) / novel.chapter_count) * 100)
    : 0;
  const firstBook = books[0];

  function startBookExtraction() {
    if (!firstBook) return;
    onStartExtraction({ scope_type: "book", book_id: firstBook.id });
  }

  return (
    <div className="workspace-page extraction-page">
      <div className="workspace-page-header">
        <div>
          <h1>Extraction</h1>
          <p>Run AI extraction across selected chapters, books, or the whole novel.</p>
        </div>
        <div className="admin-header-actions">
          <button type="button" onClick={() => setIsModalOpen(true)} disabled={!chapters.length || isRunningExtraction}>
            New Extraction
          </button>
        </div>
      </div>

      <section className="workspace-page-body">
        <section className="admin-stat-grid workspace-stats">
          <StatCard label="Books" value={books.length} detail="Uploaded" tone="blue" />
          <StatCard label="Chapters" value={novel?.chapter_count || chapters.length} detail="Total chapters" tone="green" />
          <StatCard label="Extracted" value={`${progress}%`} detail={`${extractedChapterCount} processed`} tone="purple" />
          <StatCard label="Queued" value={queuedRuns} detail="Runs" tone="orange" />
          <StatCard label="Failed" value={failedRuns} detail="Runs" tone="red" />
        </section>

        <section className="extraction-layout-grid">
          <ActiveExtractionProgress activeRun={activeRun} isRunningExtraction={isRunningExtraction} />

          <section className="admin-panel">
            <div className="admin-section-header">
              <h2>All Extraction Runs</h2>
              <span>{extractionRuns.length} runs</span>
            </div>
            <div className="extraction-run-list">
              {extractionRuns.length ? (
                extractionRuns.slice(0, 8).map((run) => <ExtractionRunCard key={run.id} run={run} />)
              ) : (
                <p className="admin-muted">No extraction runs yet.</p>
              )}
            </div>
          </section>

          <section className="admin-panel extraction-progress-card">
            <div className="admin-section-header">
              <h2>Overall Extraction Progress</h2>
              <span>{progress}%</span>
            </div>
            <ProgressBar value={progress} />
            <p className="admin-muted">
              Progress is based on completed extraction runs. Re-running the same chapters may temporarily over-count
              until chapter-level extraction status is added.
            </p>
          </section>

          <section className="admin-panel">
            <div className="admin-section-header">
              <h2>Extraction Actions</h2>
              <span>{completedRuns} completed</span>
            </div>
            <div className="extraction-action-grid">
              <button type="button" onClick={startBookExtraction} disabled={!firstBook || isRunningExtraction}>
                <strong>Extract First Book</strong>
                <span>{firstBook ? `Book ${firstBook.number}` : "No books uploaded"}</span>
              </button>
              <button type="button" onClick={() => setIsModalOpen(true)} disabled={!chapters.length || isRunningExtraction}>
                <strong>Extract Chapter Range</strong>
                <span>Select book and chapter numbers</span>
              </button>
              <button
                type="button"
                onClick={() => onStartExtraction({ scope_type: "novel" })}
                disabled={!chapters.length || isRunningExtraction}
              >
                <strong>Extract Entire Novel</strong>
                <span>All books and chapters</span>
              </button>
              <button
                type="button"
                onClick={() => onStartExtraction({ scope_type: "retry_failed" })}
                disabled={failedRuns === 0 || isRunningExtraction}
              >
                <strong>Retry Failed Chapters</strong>
                <span>{failedRuns} failed runs</span>
              </button>
            </div>
          </section>
        </section>
      </section>

      {isModalOpen ? (
        <NewExtractionModal
          books={books}
          chapters={chapters}
          onClose={() => setIsModalOpen(false)}
          onStart={onStartExtraction}
        />
      ) : null}
    </div>
  );
}
