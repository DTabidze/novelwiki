import React from "react";
import {
  Ban,
  FileSearch,
  MoreHorizontal,
  RotateCcw,
  StepForward,
  Trash2,
} from "lucide-react";
import { chapterLabel as formatChapterLabel } from "../../utils/wikiFormat.js";
import { runProgress, runTitle } from "./extractionUtils.js";

export function relativeRunTime(value) {
  if (!value) {
    return "Queued";
  }

  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return "Just now";
}

export function compactRunTitle(run) {
  return runTitle(run).replace(": ", " · ");
}

export function formatDuration(startedAt, finishedAt) {
  if (!startedAt || !finishedAt) return "-";

  const seconds = Math.max(0, Math.floor((new Date(finishedAt) - new Date(startedAt)) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`;
  }

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }

  return `${remainingSeconds}s`;
}

export function estimateRemaining(run) {
  if (run.status !== "running") return null;

  const completed = (run.run_chapters || []).filter((runChapter) =>
    runChapter.status === "completed" && runChapter.started_at && runChapter.finished_at
  );

  if (!completed.length) return null;

  const totalSeconds = completed.reduce((sum, runChapter) => (
    sum + Math.max(0, Math.floor((new Date(runChapter.finished_at) - new Date(runChapter.started_at)) / 1000))
  ), 0);
  const secondsPerChapter = totalSeconds / completed.length;
  const activeCount = (run.run_chapters || []).filter((runChapter) => runChapter.status === "processing").length;
  const remaining = Math.max((run.total_chapters || 0) - (run.completed_chapters || 0) - activeCount, 0);
  const estimatedSeconds = Math.round(secondsPerChapter * remaining);

  return formatDuration(new Date(0).toISOString(), new Date(estimatedSeconds * 1000).toISOString());
}

export function chapterLabel(runChapter) {
  const chapter = runChapter?.chapter;

  if (!chapter) return "Unknown chapter";

  return formatChapterLabel(chapter);
}

export function chapterRangeLabel(runChapters, emptyLabel = "None") {
  const chapterNumbers = runChapters
    .map((runChapter) => runChapter.chapter?.chapter_number)
    .filter((number) => Number.isFinite(Number(number)))
    .sort((a, b) => a - b);

  if (!chapterNumbers.length) return emptyLabel;

  const first = chapterNumbers[0];
  const last = chapterNumbers[chapterNumbers.length - 1];

  if (first === last) return `Chapter ${first}`;

  return `Chapters ${first}-${last}`;
}

export function requestedRangeLabel(run) {
  const runChapters = run.run_chapters || [];

  if (run.chapter_start && run.chapter_end) {
    return run.chapter_start === run.chapter_end
      ? `Chapter ${run.chapter_start}`
      : `Chapters ${run.chapter_start}-${run.chapter_end}`;
  }

  return chapterRangeLabel(runChapters, "No chapters requested");
}

export function completedRangeLabel(run) {
  return chapterRangeLabel(
    (run.run_chapters || []).filter((runChapter) => runChapter.status === "completed"),
    "None",
  );
}

export function failedRunChapter(run) {
  return (run.run_chapters || []).find((runChapter) => runChapter.status === "failed") || null;
}

export function cancelledRunChapter(run) {
  return (run.run_chapters || []).find((runChapter) => runChapter.status === "cancelled") ||
    (run.run_chapters || []).find((runChapter) => runChapter.status === "processing") ||
    (run.current_chapter_id
      ? (run.run_chapters || []).find((runChapter) => runChapter.chapter_id === run.current_chapter_id)
      : null) ||
    (run.run_chapters || []).find((runChapter) => runChapter.status === "skipped") ||
    null;
}

export function currentRunChapter(run) {
  return (run.run_chapters || []).find((runChapter) => runChapter.status === "processing") ||
    (run.run_chapters || []).find((runChapter) => runChapter.chapter_id === run.current_chapter_id) ||
    null;
}

export function RunStatusDetails({ run, warningCount }) {
  const recordsLabel = `${run.created_records_count || 0} records created`;
  const warningsLabel = `${warningCount} warning${warningCount === 1 ? "" : "s"}`;
  const requestedLabel = `Requested Range: ${requestedRangeLabel(run)}`;
  const completedLabel = `Completed Range: ${completedRangeLabel(run)}`;

  if (run.status === "failed") {
    const failedChapter = failedRunChapter(run);

    return (
      <div className="extraction-run-details">
        <b>{run.status}</b>
        <span className="run-detail-wide">{requestedLabel}</span>
        <span className="run-detail-wide">{completedLabel}</span>
        <span className="run-detail-wide">Failed at: {chapterLabel(failedChapter)}</span>
        <span>{recordsLabel}</span>
        <span className={warningCount > 0 ? "has-warnings" : ""}>{warningsLabel}</span>
      </div>
    );
  }

  if (run.status === "running") {
    const currentChapter = currentRunChapter(run);
    const activeCount = currentChapter ? 1 : 0;
    const remaining = Math.max((run.total_chapters || 0) - (run.completed_chapters || 0) - activeCount, 0);
    const eta = estimateRemaining(run);

    return (
      <div className="extraction-run-details">
        <b>{run.status}</b>
        <span className="run-detail-wide">{requestedLabel}</span>
        <span className="run-detail-wide">{completedLabel}</span>
        {currentChapter ? <span className="run-detail-wide">Current: {chapterLabel(currentChapter)}</span> : null}
        <span>Remaining: {remaining} chapter{remaining === 1 ? "" : "s"}</span>
        <span>{recordsLabel}</span>
        <span className={warningCount > 0 ? "has-warnings" : ""}>{warningsLabel}</span>
        {eta ? <span>ETA: {eta}</span> : null}
      </div>
    );
  }

  if (run.status === "completed") {
    return (
      <div className="extraction-run-details">
        <b>{run.status}</b>
        <span className="run-detail-wide">{requestedLabel}</span>
        <span className="run-detail-wide">{completedLabel}</span>
        <span>{recordsLabel}</span>
        <span className={warningCount > 0 ? "has-warnings" : ""}>{warningsLabel}</span>
        <span>Duration: {formatDuration(run.started_at, run.finished_at)}</span>
      </div>
    );
  }

  if (run.status === "cancelled") {
    const cancelledChapter = cancelledRunChapter(run);

    return (
      <div className="extraction-run-details">
        <b>Canceled</b>
        <span className="run-detail-wide">{requestedLabel}</span>
        <span className="run-detail-wide">{completedLabel}</span>
        {cancelledChapter ? <span className="run-detail-wide">Canceled at: {chapterLabel(cancelledChapter)}</span> : null}
        <span>{recordsLabel}</span>
        <span className={warningCount > 0 ? "has-warnings" : ""}>{warningsLabel}</span>
      </div>
    );
  }

  return (
    <div className="extraction-run-details">
      <b>{run.status}</b>
      <span className="run-detail-wide">{requestedLabel}</span>
      <span className="run-detail-wide">{completedLabel}</span>
      <span>{recordsLabel}</span>
      <span className={warningCount > 0 ? "has-warnings" : ""}>{warningsLabel}</span>
    </div>
  );
}

function actionsForRun(run, canContinueFromNextChapter = false) {
  const status = run.status;
  const actions = [
    {
      key: "details",
      label: "View Details",
      icon: FileSearch,
    },
  ];

  if (status === "completed") {
    actions.push(
      {
        key: "records",
        label: "View Review Items",
        icon: FileSearch,
      },
    );

    if (canContinueFromNextChapter) {
      actions.push({
        key: "continue_next",
        label: "Continue Next",
        icon: StepForward,
      });
    }

    actions.push(
      {
        key: "delete",
        label: "Delete Run",
        icon: Trash2,
        destructive: true,
      },
    );
  }

  if (status === "failed") {
    actions.push(
      {
        key: "continue",
        label: "Continue From Failure",
        icon: RotateCcw,
      },
      {
        key: "delete",
        label: "Delete Run",
        icon: Trash2,
        destructive: true,
      },
    );
  }

  if (status === "running" || status === "queued") {
    actions.push({
      key: "cancel",
      label: "Cancel Extraction",
      icon: Ban,
      destructive: true,
    });
  }

  return actions;
}

export default function ExtractionRunCard({
  run,
  onCancelRun,
  canContinueFromNextChapter,
  onContinueRun,
  onDeleteRun,
  onViewCreatedRecords,
  onViewDetails,
}) {
  const progress = runProgress(run);
  const warningCount = run.warning_count || 0;
  const [isMenuOpen, setIsMenuOpen] = React.useState(false);
  const menuRef = React.useRef(null);
  const actions = actionsForRun(run, canContinueFromNextChapter);

  React.useEffect(() => {
    if (!isMenuOpen) return undefined;

    function closeOnOutsideClick(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    }

    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isMenuOpen]);

  function handleAction(actionKey) {
    setIsMenuOpen(false);

    if (actionKey === "details") {
      onViewDetails?.(run);
    } else if (actionKey === "records") {
      onViewCreatedRecords?.(run);
    } else if (actionKey === "continue") {
      onContinueRun?.(run);
    } else if (actionKey === "continue_next") {
      onContinueRun?.(run, { fromNextChapter: true });
    } else if (actionKey === "cancel") {
      onCancelRun?.(run);
    } else if (actionKey === "delete") {
      onDeleteRun?.(run);
    }
  }

  return (
    <article className={`extraction-run-card ${run.status}`}>
      <div className="extraction-run-header">
        <strong title={runTitle(run)}>{compactRunTitle(run)}</strong>
        <span>{relativeRunTime(run.finished_at || run.started_at || run.created_at)}</span>
        <div className="extraction-run-actions" ref={menuRef}>
          <button
            className="admin-icon-button extraction-run-menu"
            type="button"
            aria-expanded={isMenuOpen}
            aria-label="Extraction run actions"
            onClick={() => setIsMenuOpen((open) => !open)}
          >
            <MoreHorizontal aria-hidden="true" size={16} strokeWidth={1.9} />
          </button>
          {isMenuOpen ? (
            <div className="extraction-run-action-menu" role="menu">
              {actions.map((action) => {
                const Icon = action.icon;

                return (
                  <button
                    key={action.key}
                    className={action.destructive ? "destructive" : ""}
                    type="button"
                    role="menuitem"
                    onClick={() => handleAction(action.key)}
                  >
                    <Icon aria-hidden="true" size={15} strokeWidth={1.9} />
                    <span>{action.label}</span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      </div>

      <RunStatusDetails run={run} warningCount={warningCount} />

      {run.error_message ? <small className="admin-danger-text extraction-run-error">{run.error_message}</small> : null}

      <div className="extraction-run-bar" aria-label={`${progress}% complete`}>
        <span style={{ width: `${progress}%` }} />
      </div>
    </article>
  );
}
