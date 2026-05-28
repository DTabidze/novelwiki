import React from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FilePenLine,
  Files,
  Hourglass,
  ListChecks,
  Play,
  Settings,
  Upload,
} from "lucide-react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function countPending(extractedData, key) {
  return (extractedData?.[key] || []).filter((record) => record.review_status === "pending").length;
}

function extractedChapterCountFromRuns(extractionRuns) {
  const chapterIds = new Set();

  extractionRuns.forEach((run) => {
    (run.run_chapters || []).forEach((runChapter) => {
      if (runChapter.status === "completed" && runChapter.chapter_id) {
        chapterIds.add(runChapter.chapter_id);
      }
    });
  });

  return chapterIds.size;
}

function relativeTime(value) {
  if (!value) return "No activity yet";

  const deltaSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  const days = Math.floor(deltaSeconds / 86400);
  const hours = Math.floor((deltaSeconds % 86400) / 3600);
  const minutes = Math.floor((deltaSeconds % 3600) / 60);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return "just now";
}

function formatScope(run) {
  if (!run) return "No extraction run";
  if (run.scope_type === "single_chapter") return "Single Chapter";
  if (run.scope_type === "chapter_range") return "Chapter Range";
  if (run.scope_type === "book") return "Entire Book";
  if (run.scope_type === "novel") return "Entire Novel";
  if (run.scope_type === "retry_failed") return "Retry From Failed Chapter";
  return run.scope_type?.replaceAll("_", " ") || "Extraction Run";
}

function latestRunTime(run) {
  if (!run) return null;
  return run.finished_at || run.started_at || run.created_at;
}

function buildRecentActivity({ books, latestRun, pendingReviewCount }) {
  const rows = [];

  if (latestRun) {
    rows.push({
      icon: CheckCircle2,
      tone: latestRun.status === "failed" ? "red" : "green",
      title: latestRun.status === "completed" ? "Extraction completed" : `Extraction ${latestRun.status}`,
      subtitle: formatScope(latestRun),
      time: relativeTime(latestRunTime(latestRun)),
      badge: latestRun.status,
    });
  }

  books
    .filter((book) => book.parsing_status === "source_replaced")
    .slice(0, 2)
    .forEach((book) => {
      rows.push({
        icon: Upload,
        tone: "blue",
        title: `Book ${book.number} source replaced`,
        subtitle: book.title,
        time: relativeTime(book.uploaded_at),
        badge: "Reparse required",
      });
    });

  books
    .filter((book) => book.parsing_status === "parsed")
    .slice(0, 2)
    .forEach((book) => {
      rows.push({
        icon: Upload,
        tone: "blue",
        title: `Book ${book.number} uploaded and parsed`,
        subtitle: book.title,
        time: relativeTime(book.uploaded_at),
        badge: `${book.chapter_count || 0} chapters`,
      });
    });

  if (pendingReviewCount > 0) {
    rows.push({
      icon: ClipboardList,
      tone: "orange",
      title: "Review queue items added",
      subtitle: "Extracted records waiting for review",
      time: "Current",
      badge: `${pendingReviewCount} items`,
    });
  }

  return rows.slice(0, 5);
}

export default function NovelWorkspaceOverview({
  books,
  extractedData,
  extractionRuns = [],
  novel,
  onOpenNovelSettings,
}) {
  const navigate = useNavigate();
  const chapterCount = novel?.chapter_count || 0;
  const bookCount = books.length || novel?.book_count || 0;
  const extractedChapterCount = extractedChapterCountFromRuns(extractionRuns);
  const extractedProgress = chapterCount
    ? Math.round((Math.min(extractedChapterCount, chapterCount) / chapterCount) * 100)
    : 0;
  const latestRun = extractionRuns[0] || null;
  const pendingCharacters = countPending(extractedData, "characters");
  const pendingMetadata = countPending(extractedData, "character_metadata_proposals");
  const pendingProgression = countPending(extractedData, "progression_events");
  const pendingSkills = countPending(extractedData, "skills") + countPending(extractedData, "character_skills");
  const pendingItems = countPending(extractedData, "items") + countPending(extractedData, "character_items");
  const pendingLifeEvents = countPending(extractedData, "life_events");
  const totalPending =
    pendingCharacters + pendingMetadata + pendingProgression + pendingSkills + pendingItems + pendingLifeEvents;
  const sourceReplacedBook = books.find((book) => book.parsing_status === "source_replaced");
  const needsExtraction = chapterCount > extractedChapterCount;
  const statusTone = novel?.status === "failed"
    ? "danger"
    : novel?.status === "draft"
      ? "warning"
      : "success";
  const recentActivity = buildRecentActivity({ books, latestRun, pendingReviewCount: totalPending });

  const summaryCards = [
    {
      icon: BookOpen,
      tone: "purple",
      label: "Books",
      value: bookCount,
      detail: "Uploaded",
      action: () => navigate("books"),
    },
    {
      icon: Files,
      tone: "green",
      label: "Chapters",
      value: chapterCount,
      detail: "Total",
      action: () => navigate("chapters"),
    },
    {
      icon: CheckCircle2,
      tone: "purple",
      label: "Extracted",
      value: extractedChapterCount,
      detail: `${extractedProgress}% of chapters`,
      action: () => navigate("extraction"),
    },
    {
      icon: Hourglass,
      tone: "orange",
      label: "Pending Review",
      value: totalPending,
      detail: "Items",
      action: () => navigate("review"),
    },
  ];

  const recommendations = [
    sourceReplacedBook
      ? {
          icon: Upload,
          tone: "purple",
          title: `Reparse Book ${sourceReplacedBook.number}`,
          text: "Source file was replaced. Reparse to generate new chapters.",
          action: () => navigate("books"),
        }
      : null,
    totalPending > 0
      ? {
          icon: ListChecks,
          tone: "orange",
          title: `Review ${totalPending} pending items`,
          text: "Extracted records are waiting in the review queue.",
          action: () => navigate("review"),
        }
      : null,
    needsExtraction
      ? {
          icon: Play,
          tone: "green",
          title: "Run extraction",
          text: "Continue extracting chapters for complete coverage.",
          action: () => navigate("extraction"),
        }
      : null,
  ].filter(Boolean);

  return (
    <div className="workspace-page overview-page">
      <section className="workspace-page-header overview-hero">
        <div>
          <div className="workspace-title-row">
            <h1 title={novel?.title}>{novel?.title || "Novel Workspace"}</h1>
            <StatusBadge tone={statusTone}>{novel?.status || "ready"}</StatusBadge>
          </div>
          {novel?.author ? <span className="workspace-author">by {novel.author}</span> : null}
          <p>Manage books, chapters, extraction, and review for this novel.</p>
        </div>
        <div className="admin-header-actions">
          <button
            className="admin-secondary-button"
            type="button"
            onClick={() => window.open(`/wiki/novels/${novel.id}`, "_blank", "noopener,noreferrer")}
          >
            View Public Wiki
            <ExternalLink aria-hidden="true" size={15} strokeWidth={1.9} />
          </button>
          <button type="button" onClick={onOpenNovelSettings}>
            Novel Settings
            <Settings aria-hidden="true" size={15} strokeWidth={1.9} />
          </button>
        </div>
      </section>

      <section className="workspace-page-body overview-page-body">
        <section className="overview-summary-grid">
          {summaryCards.map((card) => (
            <button className="overview-summary-card" key={card.label} type="button" onClick={card.action}>
              <span className={`overview-summary-icon ${card.tone}`}>
                <card.icon aria-hidden="true" size={24} strokeWidth={1.85} />
              </span>
              <span>
                <strong>{card.value}</strong>
                <em>{card.label}</em>
                <small>{card.detail}</small>
              </span>
              <ArrowRight aria-hidden="true" size={18} strokeWidth={1.9} />
            </button>
          ))}
        </section>

        <section className="overview-main-grid">
          <section className="admin-panel overview-activity-panel">
            <div className="admin-section-header">
              <h2>Recent Activity</h2>
              <button className="admin-text-button" type="button" onClick={() => navigate("extraction")}>
                View all activity
              </button>
            </div>
            <div className="overview-activity-list">
              {recentActivity.length ? recentActivity.map((activity) => (
                <article className="overview-activity-row" key={`${activity.title}-${activity.subtitle}`}>
                  <span className={`overview-activity-icon ${activity.tone}`}>
                    <activity.icon aria-hidden="true" size={17} strokeWidth={1.9} />
                  </span>
                  <span className="overview-activity-copy">
                    <strong>{activity.title}</strong>
                    <small>{activity.subtitle}</small>
                  </span>
                  <time>{activity.time}</time>
                  <span className={`overview-activity-badge ${activity.tone}`}>{activity.badge}</span>
                </article>
              )) : (
                <p className="admin-muted">No activity yet. Upload a book to start this workspace.</p>
              )}
            </div>
          </section>

          <aside className="overview-side-column">
            <section className="admin-panel overview-active-run-panel">
              <div className="admin-section-header">
                <h2>Active Extraction Run</h2>
                <button className="admin-text-button" type="button" onClick={() => navigate("extraction")}>
                  View all runs
                </button>
              </div>
              {latestRun ? (
                <div className="overview-run-summary">
                  <strong>{formatScope(latestRun)}</strong>
                  <span>Started {relativeTime(latestRun.started_at || latestRun.created_at)}</span>
                  <div className="overview-run-progress">
                    <ProgressBar value={latestRun.total_chapters ? (latestRun.completed_chapters / latestRun.total_chapters) * 100 : 0} />
                    <em>{latestRun.total_chapters ? Math.round((latestRun.completed_chapters / latestRun.total_chapters) * 100) : 0}%</em>
                  </div>
                  <small>
                    Completed {latestRun.completed_chapters || 0} / {latestRun.total_chapters || 0} chapters
                  </small>
                </div>
              ) : (
                <p className="admin-muted">No extraction runs yet. Start from a book, range, chapter, or full novel.</p>
              )}
            </section>

            <section className="admin-panel overview-actions-panel">
              <div className="admin-section-header">
                <h2>Quick Actions</h2>
              </div>
              <div className="overview-action-grid">
                <button type="button" onClick={() => navigate("books?upload=1")}>
                  <Upload aria-hidden="true" size={18} strokeWidth={1.9} />
                  <span><strong>Upload Book</strong><small>Add a new source file</small></span>
                </button>
                <button type="button" onClick={() => navigate("extraction?new=1")}>
                  <Play aria-hidden="true" size={18} strokeWidth={1.9} />
                  <span><strong>Run Extraction</strong><small>Start a new extraction run</small></span>
                </button>
                <button type="button" onClick={() => navigate("review")}>
                  <ListChecks aria-hidden="true" size={18} strokeWidth={1.9} />
                  <span><strong>Open Review Queue</strong><small>Review pending items</small></span>
                </button>
                <button type="button" onClick={() => navigate("chapters")}>
                  <BookOpen aria-hidden="true" size={18} strokeWidth={1.9} />
                  <span><strong>Inspect Chapters</strong><small>Browse parsed chapters</small></span>
                </button>
              </div>
            </section>
          </aside>
        </section>

        <section className="admin-panel overview-next-panel">
          <div className="admin-section-header">
            <h2>Next Up / Recommended</h2>
          </div>
          <div className="overview-next-grid">
            {recommendations.length ? recommendations.map((item) => (
              <button className="overview-next-card" key={item.title} type="button" onClick={item.action}>
                <span className={`overview-summary-icon ${item.tone}`}>
                  <item.icon aria-hidden="true" size={18} strokeWidth={1.9} />
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.text}</small>
                </span>
                <ArrowRight aria-hidden="true" size={18} strokeWidth={1.9} />
              </button>
            )) : (
              <article className="overview-next-empty">
                <FilePenLine aria-hidden="true" size={18} strokeWidth={1.9} />
                <span>
                  <strong>Workspace is up to date</strong>
                  <small>No immediate recommendations.</small>
                </span>
              </article>
            )}
          </div>
        </section>
      </section>
    </div>
  );
}
