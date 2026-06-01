import React from "react";
import { useSearchParams } from "react-router-dom";
import ActiveExtractionProgress from "./ActiveExtractionProgress.jsx";
import ExtractionRunsPanel from "./ExtractionRunsPanel.jsx";
import ExtractionStatsRow from "./ExtractionStatsRow.jsx";
import NewExtractionModal from "./NewExtractionModal.jsx";
import { extractionProgressFromRuns } from "./extractionUtils.js";

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
  onStopExtraction,
  onDeleteExtractionRun,
  onViewReviewItems,
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [modalDefaults, setModalDefaults] = React.useState(null);
  const activeRun = latestRunWithStatus(extractionRuns, "running");
  const focusRun = activeRun || extractionRuns[0] || null;
  const failedRuns = countRuns(extractionRuns, "failed");
  const queuedRuns = countRuns(extractionRuns, "queued");
  const chapterCount = novel?.chapter_count || chapters.length;
  const { extractedChapterCount, progress } = extractionProgressFromRuns(
    extractionRuns,
    chapterCount,
  );

  function retryFromFailedRun(run) {
    return onStartExtraction({
      scope_type: "retry_failed",
      source_run_id: run.id,
    });
  }

  function closeNewExtractionModal() {
    setIsModalOpen(false);
    setModalDefaults(null);
    setSearchParams({});
  }

  function continueFromNextChapter(run) {
    if (!run.book_id || !run.chapter_end) return;

    setModalDefaults({
      bookId: String(run.book_id),
      chapterStart: String(run.chapter_end + 1),
      scopeType: "chapter_range",
    });
    setIsModalOpen(true);
  }

  function canContinueFromNextChapter(run) {
    if (run.status !== "completed" || !run.book_id || !run.chapter_end) return false;

    return chapters.some((chapter) =>
      Number(chapter.book_id) === Number(run.book_id) &&
      Number(chapter.chapter_number) > Number(run.chapter_end)
    );
  }

  React.useEffect(() => {
    if (searchParams.get("new") === "1") {
      setIsModalOpen(true);
    }
  }, [searchParams]);

  return (
    <div className="workspace-page extraction-page">
      <div className="workspace-page-header">
        <div>
          <h1>Extraction</h1>
          <p>Run AI extraction across selected chapters, books, or the whole novel.</p>
        </div>
      </div>

      <section className="workspace-page-body">
        <ExtractionStatsRow
          bookCount={books.length}
          chapterCount={chapterCount}
          extractedChapterCount={extractedChapterCount}
          failedRuns={failedRuns}
          progress={progress}
          queuedRuns={queuedRuns}
        />

        <section className="extraction-layout-grid">
          <ActiveExtractionProgress
            focusRun={focusRun}
            isRunningExtraction={isRunningExtraction}
            onRetryRun={retryFromFailedRun}
            onStopRun={onStopExtraction}
          />
          <ExtractionRunsPanel
            canContinueFromNextChapter={canContinueFromNextChapter}
            extractionRuns={extractionRuns}
            onCancelRun={onStopExtraction}
            onContinueFromNextChapter={continueFromNextChapter}
            onContinueRun={retryFromFailedRun}
            onDeleteRun={onDeleteExtractionRun}
            onNewExtraction={() => setIsModalOpen(true)}
            onViewReviewItems={onViewReviewItems}
          />
        </section>
      </section>

      {isModalOpen ? (
        <NewExtractionModal
          books={books}
          chapters={chapters}
          extractionRuns={extractionRuns}
          initialValues={modalDefaults}
          onClose={closeNewExtractionModal}
          onStart={onStartExtraction}
        />
      ) : null}
    </div>
  );
}
