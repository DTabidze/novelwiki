import React from "react";
import { Ban, FileSearch, Trash2, X } from "lucide-react";
import ExtractionRunCard, {
  cancelledRunChapter,
  chapterLabel,
  completedRangeLabel,
  currentRunChapter,
  failedRunChapter,
  formatDuration,
  requestedRangeLabel,
} from "./ExtractionRunCard.jsx";
import { runTitle } from "./extractionUtils.js";

const RUNS_PER_PAGE = 6;

function DetailRow({ label, value, danger = false }) {
  if (!value) return null;

  return (
    <p className={danger ? "danger" : ""}>
      <span>{label}</span>
      <strong>{value}</strong>
    </p>
  );
}

function ExtractionRunDetailsModal({ run, onClose }) {
  const warningCount = run.warning_count || 0;
  const failedChapter = failedRunChapter(run);
  const cancelledChapter = cancelledRunChapter(run);
  const currentChapter = currentRunChapter(run);

  return (
    <div className="extraction-action-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="extraction-action-modal extraction-run-details-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="extraction-run-details-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <span className="modal-icon info">
            <FileSearch aria-hidden="true" size={18} strokeWidth={1.9} />
          </span>
          <div>
            <h3 id="extraction-run-details-title">Extraction Run Details</h3>
            <p>{runTitle(run)}</p>
          </div>
          <button className="admin-icon-button" type="button" aria-label="Close details" onClick={onClose}>
            <X aria-hidden="true" size={18} strokeWidth={1.9} />
          </button>
        </header>

        <div className="extraction-run-detail-grid">
          <DetailRow label="Status" value={run.status === "cancelled" ? "Canceled" : run.status} />
          <DetailRow label="Requested Range" value={requestedRangeLabel(run)} />
          <DetailRow label="Completed Range" value={completedRangeLabel(run)} />
          <DetailRow label="Current Chapter" value={currentChapter ? chapterLabel(currentChapter) : null} />
          <DetailRow label="Failed At" value={failedChapter ? chapterLabel(failedChapter) : null} danger />
          <DetailRow label="Canceled At" value={cancelledChapter ? chapterLabel(cancelledChapter) : null} />
          <DetailRow label="Records Created" value={`${run.created_records_count || 0}`} />
          <DetailRow label="Warnings" value={`${warningCount}`} danger={warningCount > 0} />
          <DetailRow label="Started" value={run.started_at ? new Date(run.started_at).toLocaleString() : "-"} />
          <DetailRow label="Finished" value={run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"} />
          <DetailRow label="Duration" value={formatDuration(run.started_at, run.finished_at)} />
          <DetailRow label="Failure Reason" value={run.error_message} danger />
        </div>
      </section>
    </div>
  );
}

function ConfirmActionModal({ action, onCancel, onConfirm }) {
  const isDelete = action.type === "delete";
  const Icon = isDelete ? Trash2 : Ban;

  return (
    <div className="extraction-action-backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        className="extraction-action-modal extraction-confirm-action-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="extraction-action-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <span className="modal-icon danger">
            <Icon aria-hidden="true" size={18} strokeWidth={1.9} />
          </span>
          <div>
            <h3 id="extraction-action-title">{isDelete ? "Delete Extraction Run" : "Cancel Extraction"}</h3>
            <p>{runTitle(action.run)}</p>
          </div>
        </header>

        <p className="extraction-action-warning">
          {isDelete
            ? "This removes the extraction run history only. Generated review items will not be deleted."
            : "This stops future chapter processing. Already-created review items will remain, and any in-flight output will be discarded if it returns after cancellation."}
        </p>

        <footer>
          <button className="admin-secondary-button" type="button" onClick={onCancel}>Cancel</button>
          <button className="admin-danger-button" type="button" onClick={onConfirm}>
            {isDelete ? "Delete Run" : "Cancel Extraction"}
          </button>
        </footer>
      </section>
    </div>
  );
}

function visiblePageNumbers(currentPage, totalPages) {
  const pages = new Set([1, totalPages, currentPage]);

  if (currentPage > 1) pages.add(currentPage - 1);
  if (currentPage < totalPages) pages.add(currentPage + 1);

  return Array.from(pages).sort((a, b) => a - b);
}

export default function ExtractionRunsPanel({
  extractionRuns,
  canContinueFromNextChapter,
  onCancelRun,
  onContinueRun,
  onContinueFromNextChapter,
  onDeleteRun,
  onNewExtraction,
  onViewReviewItems,
}) {
  const [detailsRun, setDetailsRun] = React.useState(null);
  const [confirmAction, setConfirmAction] = React.useState(null);
  const [page, setPage] = React.useState(1);
  const totalPages = Math.max(1, Math.ceil(extractionRuns.length / RUNS_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * RUNS_PER_PAGE;
  const endIndex = Math.min(startIndex + RUNS_PER_PAGE, extractionRuns.length);
  const visibleRuns = extractionRuns.slice(startIndex, endIndex);
  const pageNumbers = visiblePageNumbers(safePage, totalPages);

  React.useEffect(() => {
    setPage((currentPage) => Math.min(currentPage, totalPages));
  }, [totalPages]);

  React.useEffect(() => {
    setPage(1);
  }, [extractionRuns[0]?.id]);

  async function confirmPendingAction() {
    const action = confirmAction;
    setConfirmAction(null);

    if (!action) return;

    if (action.type === "cancel") {
      await onCancelRun?.(action.run);
    } else if (action.type === "delete") {
      await onDeleteRun?.(action.run);
    }
  }

  return (
    <section className="admin-panel extraction-runs-panel">
      <div className="admin-section-header">
        <div>
          <h2>All Extraction Runs</h2>
          <p>Recent processing jobs and outcomes.</p>
        </div>
        <button type="button" onClick={onNewExtraction}>New Extraction</button>
      </div>
      <div className="extraction-run-list">
        {extractionRuns.length ? (
          visibleRuns.map((run) => (
            <ExtractionRunCard
              key={run.id}
              run={run}
              canContinueFromNextChapter={canContinueFromNextChapter?.(run)}
              onCancelRun={(selectedRun) => setConfirmAction({ type: "cancel", run: selectedRun })}
              onContinueRun={(selectedRun, options) => {
                if (options?.fromNextChapter) {
                  onContinueFromNextChapter?.(selectedRun);
                } else {
                  onContinueRun?.(selectedRun);
                }
              }}
              onDeleteRun={(selectedRun) => setConfirmAction({ type: "delete", run: selectedRun })}
              onViewCreatedRecords={onViewReviewItems}
              onViewDetails={setDetailsRun}
            />
          ))
        ) : (
          <p className="admin-muted">No extraction runs yet.</p>
        )}
      </div>
      {extractionRuns.length > RUNS_PER_PAGE ? (
        <div className="extraction-run-pagination">
          <p>
            Showing {startIndex + 1}-{endIndex} of {extractionRuns.length} runs.
          </p>
          <div>
            <button
              className="admin-secondary-button"
              type="button"
              disabled={safePage === 1}
              onClick={() => setPage((currentPage) => Math.max(currentPage - 1, 1))}
            >
              Prev
            </button>
            {pageNumbers.map((pageNumber) => (
              <button
                key={pageNumber}
                className={pageNumber === safePage ? "admin-secondary-button active" : "admin-secondary-button"}
                type="button"
                aria-current={pageNumber === safePage ? "page" : undefined}
                onClick={() => setPage(pageNumber)}
              >
                {pageNumber}
              </button>
            ))}
            <button
              className="admin-secondary-button"
              type="button"
              disabled={safePage === totalPages}
              onClick={() => setPage((currentPage) => Math.min(currentPage + 1, totalPages))}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
      {detailsRun ? <ExtractionRunDetailsModal run={detailsRun} onClose={() => setDetailsRun(null)} /> : null}
      {confirmAction ? (
        <ConfirmActionModal
          action={confirmAction}
          onCancel={() => setConfirmAction(null)}
          onConfirm={confirmPendingAction}
        />
      ) : null}
    </section>
  );
}
