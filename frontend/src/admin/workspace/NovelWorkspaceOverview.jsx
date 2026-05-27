import React from "react";
import { useNavigate } from "react-router-dom";
import ProgressBar from "../components/ProgressBar.jsx";
import StatCard from "../components/StatCard.jsx";
import BookListPanel from "./BookListPanel.jsx";

function countPending(extractedData, key) {
  return (extractedData?.[key] || []).filter((record) => record.review_status === "pending").length;
}

function countWarnings(extractedData) {
  const warningKeys = ["progression_events", "character_metadata_proposals"];

  return warningKeys.reduce(
    (sum, key) =>
      sum +
      (extractedData?.[key] || []).filter((record) => (record.review_warnings || []).length > 0).length,
    0
  );
}

function extractedChapterCountFromRuns(extractionRuns) {
  return extractionRuns
    .filter((run) => run.status === "completed")
    .reduce((sum, run) => sum + (run.completed_chapters || 0), 0);
}

function latestExtractionRun(extractionRuns) {
  return extractionRuns[0] || null;
}

export default function NovelWorkspaceOverview({ books, extractedData, extractionRuns = [], novel }) {
  const navigate = useNavigate();
  const chapterCount = novel?.chapter_count || 0;
  const bookCount = books.length || novel?.book_count || 0;
  const extractedChapterCount = extractedChapterCountFromRuns(extractionRuns);
  const extractedProgress = chapterCount
    ? Math.round((Math.min(extractedChapterCount, chapterCount) / chapterCount) * 100)
    : 0;
  const latestRun = latestExtractionRun(extractionRuns);
  const pendingCharacters = countPending(extractedData, "characters");
  const pendingMetadata = countPending(extractedData, "character_metadata_proposals");
  const pendingProgression = countPending(extractedData, "progression_events");
  const pendingSkills = countPending(extractedData, "skills") + countPending(extractedData, "character_skills");
  const pendingItems = countPending(extractedData, "items") + countPending(extractedData, "character_items");
  const pendingLifeEvents = countPending(extractedData, "life_events");
  const totalPending =
    pendingCharacters + pendingMetadata + pendingProgression + pendingSkills + pendingItems + pendingLifeEvents;
  const warnings = countWarnings(extractedData);
  const statusTone = novel?.status === "failed"
    ? "danger"
    : novel?.status === "draft"
      ? "warning"
      : "success";

  return (
    <div className="workspace-page overview-page">
      <section className="workspace-page-header">
        <div>
          <div className="workspace-title-row">
            <h1>{novel?.title || "Novel Workspace"}</h1>
            <span className={`admin-status-badge ${statusTone}`}>{novel?.status || "ready"}</span>
          </div>
          {novel?.author ? <span className="workspace-author">by {novel.author}</span> : null}
          <p>{novel?.description || "Manage books, chapters, extraction, and review for this novel."}</p>
        </div>
        <div className="admin-header-actions">
          <button
            className="admin-secondary-button"
            type="button"
            onClick={() => window.open(`/wiki/novels/${novel.id}`, "_blank", "noopener,noreferrer")}
          >
            View Public Wiki
          </button>
          <button type="button" disabled>
            Novel Settings
          </button>
        </div>
      </section>

      <section className="workspace-page-body overview-page-body">
        <section className="admin-stat-grid workspace-stats">
          <StatCard label="Books" value={bookCount} detail="Uploaded" tone="blue" />
          <StatCard label="Chapters" value={chapterCount} detail="Total chapters" tone="green" />
          <StatCard label="Extracted" value={extractedChapterCount} detail={`${extractedProgress}% completed`} tone="purple" />
          <StatCard label="Pending Review" value={totalPending} detail="Items" tone="orange" />
          <StatCard label="Warnings" value={warnings} detail="Need attention" tone="red" />
        </section>

        <section className="workspace-grid">
          <BookListPanel books={books} />

          <section className="admin-panel">
            <div className="admin-section-header">
              <h2>Extraction Progress</h2>
              <span>{extractedProgress}%</span>
            </div>
            <ProgressBar value={extractedProgress} />
            {latestRun ? (
              <p className="admin-muted">
                Latest run: {latestRun.scope_type.replaceAll("_", " ")} · {latestRun.status} ·{" "}
                {latestRun.completed_chapters}/{latestRun.total_chapters} chapters.
              </p>
            ) : (
              <p className="admin-muted">No extraction runs yet. Start with a book, range, chapter, or full novel.</p>
            )}
          </section>

          <section className="admin-panel">
            <div className="admin-section-header">
              <h2>Pending Review By Type</h2>
              <span>{totalPending} total</span>
            </div>
            <div className="pending-type-grid">
              <span>Characters <strong>{pendingCharacters}</strong></span>
              <span>Metadata <strong>{pendingMetadata}</strong></span>
              <span>Progression <strong>{pendingProgression}</strong></span>
              <span>Skills <strong>{pendingSkills}</strong></span>
              <span>Items <strong>{pendingItems}</strong></span>
              <span>Life Events <strong>{pendingLifeEvents}</strong></span>
            </div>
          </section>

          <section className="admin-panel">
            <div className="admin-section-header">
              <h2>Quick Actions</h2>
              <span>Workspace</span>
            </div>
            <div className="workspace-action-grid">
              <button type="button" onClick={() => navigate("books")}>Upload Book</button>
              <button type="button" onClick={() => navigate("chapters")}>Inspect Chapters</button>
              <button type="button" onClick={() => navigate("extraction")}>Run Extraction</button>
              <button type="button" onClick={() => navigate("review")}>Review Queue</button>
            </div>
          </section>
        </section>
      </section>
    </div>
  );
}
