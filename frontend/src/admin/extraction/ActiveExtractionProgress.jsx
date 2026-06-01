import React from "react";
import { BookOpen, RotateCcw, Square } from "lucide-react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import ExtractionStatusIcon from "./ExtractionStatusIcon.jsx";
import { formatRunDate, runProgress, runTitle, statusTone } from "./extractionUtils.js";

function summaryValue(run, key) {
  const summary = run?.summary || {};
  return summary[key] || 0;
}

function formatDuration(startedAt, finishedAt) {
  if (!startedAt) return "-";

  const endTime = finishedAt ? new Date(finishedAt) : new Date();
  const seconds = Math.max(0, Math.floor((endTime - new Date(startedAt)) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function estimateRemaining(run) {
  if (!run || run.status !== "running") {
    return "-";
  }

  const completedRunChapters = (run.run_chapters || []).filter((runChapter) =>
    runChapter.status === "completed" &&
    runChapter.started_at &&
    runChapter.finished_at
  );

  if (!completedRunChapters.length) {
    return "-";
  }

  const totalCompletedSeconds = completedRunChapters.reduce((sum, runChapter) => {
    return sum + Math.max(0, Math.floor((new Date(runChapter.finished_at) - new Date(runChapter.started_at)) / 1000));
  }, 0);
  const secondsPerChapter = totalCompletedSeconds / completedRunChapters.length;
  const remainingChapters = Math.max((run.total_chapters || 0) - run.completed_chapters, 0);
  const estimatedSeconds = Math.round(secondsPerChapter * remainingChapters);
  const hours = Math.floor(estimatedSeconds / 3600);
  const minutes = Math.floor((estimatedSeconds % 3600) / 60);
  const seconds = estimatedSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function ExtractionRunHeader({ isActive, run }) {
  return (
    <div className="extraction-operation-header">
      <div className="extraction-run-title-line">
        <div>
          <h3>
            <span className="extraction-book-icon">
              <BookOpen aria-hidden="true" size={17} strokeWidth={1.9} />
            </span>
            {runTitle(run)}
          </h3>
          <p>
            {run.chapter_start && run.chapter_end
              ? `${isActive ? "Extracting" : "Extracted"} Chapters ${run.chapter_start}-${run.chapter_end} (${run.total_chapters} chapters)`
              : "Selected extraction scope"}
          </p>
        </div>
        <StatusBadge tone={statusTone(run.status)}>{run.status}</StatusBadge>
      </div>
    </div>
  );
}

function ExtractionProgressHero({ progress, run }) {
  return (
    <div className="extraction-progress-hero">
      <div className="extraction-progress-mainline">
        <div>
          <strong className="extraction-progress-number">{progress}%</strong>
          <span className="admin-muted">
            {run.completed_chapters} / {run.total_chapters} chapters completed
          </span>
        </div>
        <div className="extraction-time-stack">
          <span>Started: <strong>{formatRunDate(run.started_at)}</strong></span>
          <span>Elapsed: <strong>{formatDuration(run.started_at, run.finished_at)}</strong></span>
          <span>Estimated remaining: <strong>{estimateRemaining(run)}</strong></span>
        </div>
      </div>
      <ProgressBar value={progress} />
    </div>
  );
}

function CurrentChapterPanel({ currentRunChapter, run }) {
  return (
    <div className="extraction-current-chapter">
      <span>Current Chapter</span>
      <strong>
        {currentRunChapter?.chapter?.title || run.current_chapter?.title || "No chapter currently processing"}
      </strong>
      <small>
        {currentRunChapter?.error_message ||
          run.error_message ||
          `${currentRunChapter?.records_created || 0} records created · ${currentRunChapter?.warning_count || 0} warnings`}
      </small>
    </div>
  );
}

function ExtractionSummaryInline({ run }) {
  const summaryItems = [
    ["Characters", summaryValue(run, "characters_created") + summaryValue(run, "characters_updated")],
    ["Progression Events", summaryValue(run, "progression_events_created")],
    ["Metadata Proposals", summaryValue(run, "metadata_proposals_created")],
    ["Skills & Items", summaryValue(run, "skills_created") + summaryValue(run, "items_created")],
  ];

  return (
    <div className="extraction-summary-inline">
      <span>Extraction Summary</span>
      <div>
        {summaryItems.map(([label, value]) => (
          <p key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
          </p>
        ))}
      </div>
    </div>
  );
}

function RecentProcessedChaptersList({ run }) {
  const runChapters = run.run_chapters || [];
  const currentIndex = Math.max(
    runChapters.findIndex((runChapter) => runChapter.status === "processing"),
    run.completed_chapters ? run.completed_chapters - 1 : 0,
  );
  const startIndex = Math.max(0, currentIndex - 5);
  const visibleChapters = runChapters.slice(startIndex, startIndex + 10);

  return (
    <div className="extraction-recent-stream">
      <h4>Recent Chapters</h4>
      <div className="extraction-stream-list">
        {visibleChapters.length ? visibleChapters.map((runChapter) => {
          const status = runChapter.status;
          const chapter = runChapter.chapter || {};
          const displayTitle = (chapter.title || "").replace(
            new RegExp(`^\\s*Chapter\\s+${chapter.chapter_number}\\s*:?\\s*`, "i"),
            "",
          ) || chapter.title;
          const isFinished = status === "completed" || status === "failed";
          const recordsText = isFinished ? `${runChapter.records_created || 0} records` : "— records";
          const warningsText = isFinished ? `${runChapter.warning_count || 0} warnings` : "— warnings";
          const durationText = isFinished ? formatDuration(runChapter.started_at, runChapter.finished_at) : "—";

          return (
            <div className={`extraction-stream-row ${status}`} key={runChapter.id}>
              <ExtractionStatusIcon className="extraction-stream-icon" status={status} />
              <strong className="extraction-stream-number">{chapter.chapter_number}</strong>
              <div className="extraction-stream-title">
                <b title={chapter.title}>{displayTitle}</b>
              </div>
              <em className="extraction-stream-records">{recordsText}</em>
              <em className="extraction-stream-warnings">⚠ {warningsText}</em>
              <em className="extraction-stream-duration">{durationText}</em>
            </div>
          );
        }) : (
          <p className="admin-muted">Chapter stream will appear after an extraction run starts.</p>
        )}
      </div>
    </div>
  );
}

function firstFailedRunChapter(run) {
  return (run?.run_chapters || []).find((runChapter) => runChapter.status === "failed") || null;
}

function ExtractionConfirmModal({ action, chapterNumber, onCancel, onConfirm }) {
  if (!action) return null;

  const isRetry = action === "retry";

  return (
    <div className="extraction-confirm-backdrop" role="presentation" onMouseDown={onCancel}>
      <div
        className="extraction-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="extraction-confirm-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <span className={isRetry ? "retry" : "stop"}>
            {isRetry ? <RotateCcw aria-hidden="true" size={20} /> : <Square aria-hidden="true" size={20} />}
          </span>
          <div>
            <h3 id="extraction-confirm-title">
              {isRetry ? `Continue from Chapter ${chapterNumber}` : "Stop Extraction"}
            </h3>
            <p>
              {isRetry
                ? `Continue extraction from Chapter ${chapterNumber} through the original run end?`
                : "Stop this extraction run? The current chapter may finish, but later chapters will be skipped."}
            </p>
          </div>
        </header>
        <footer>
          <button type="button" className="admin-secondary-button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className={isRetry ? "" : "admin-danger-button"}
            onClick={onConfirm}
          >
            {isRetry ? "Continue Extraction" : "Stop Extraction"}
          </button>
        </footer>
      </div>
    </div>
  );
}

export default function ActiveExtractionProgress({ focusRun, isRunningExtraction, onRetryRun, onStopRun }) {
  const [confirmAction, setConfirmAction] = React.useState(null);
  const fallbackRunning = isRunningExtraction && !focusRun;
  const progress = runProgress(focusRun);
  const isActive = focusRun?.status === "running" || fallbackRunning;
  const canStop = focusRun && ["queued", "running"].includes(focusRun.status);
  const failedRunChapter = firstFailedRunChapter(focusRun);
  const failedChapterNumber = failedRunChapter?.chapter?.chapter_number || focusRun?.chapter_start;
  const canRetry = focusRun?.status === "failed" && failedRunChapter;
  const currentRunChapter = focusRun?.run_chapters?.find((runChapter) => runChapter.status === "processing") ||
    focusRun?.run_chapters?.find((runChapter) => runChapter.chapter_id === focusRun.current_chapter_id) ||
    [...(focusRun?.run_chapters || [])].reverse().find((runChapter) =>
      ["completed", "failed"].includes(runChapter.status)
    );

  return (
    <section className="admin-panel extraction-active-panel">
      <div className="admin-section-header">
        <h2>Active Extraction Progress</h2>
        <div className="extraction-panel-actions">
          {canRetry ? (
            <button
              className="admin-secondary-button"
              type="button"
              onClick={() => setConfirmAction("retry")}
            >
              Continue from Chapter {failedChapterNumber}
            </button>
          ) : null}
          {canStop ? (
            <button
              className="admin-danger-button"
              type="button"
              onClick={() => setConfirmAction("stop")}
            >
              Stop Extraction
            </button>
          ) : null}
        </div>
      </div>

      {focusRun ? (
        <>
          <ExtractionRunHeader isActive={isActive} run={focusRun} />
          <ExtractionProgressHero progress={progress} run={focusRun} />
          <div className="extraction-operation-split">
            <CurrentChapterPanel currentRunChapter={currentRunChapter} run={focusRun} />
            <ExtractionSummaryInline run={focusRun} />
          </div>
          <RecentProcessedChaptersList run={focusRun} />
        </>
      ) : (
        <div className="extraction-idle-state">
          <strong>{fallbackRunning ? "Extraction request is running" : "No active extraction run"}</strong>
          <p className="admin-muted">
            {fallbackRunning
              ? "The extraction run has started and live chapter progress will appear here."
              : "Start a book, range, single chapter, or full novel extraction from the actions panel."}
          </p>
        </div>
      )}
      <ExtractionConfirmModal
        action={confirmAction}
        chapterNumber={failedChapterNumber}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          const action = confirmAction;
          setConfirmAction(null);

          if (action === "retry") {
            onRetryRun(focusRun);
          }

          if (action === "stop") {
            onStopRun(focusRun);
          }
        }}
      />
    </section>
  );
}
