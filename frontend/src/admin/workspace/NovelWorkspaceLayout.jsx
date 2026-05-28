import React from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../../api.js";
import BooksPage from "../books/BooksPage.jsx";
import ChaptersPage from "../chapters/ChaptersPage.jsx";
import EmptyState from "../components/EmptyState.jsx";
import ExtractionPage from "../extraction/ExtractionPage.jsx";
import EditNovelModal from "../novels/EditNovelModal.jsx";
import WorkspaceSidebar from "./WorkspaceSidebar.jsx";
import NovelWorkspaceOverview from "./NovelWorkspaceOverview.jsx";

function WorkspacePlaceholder({ title, message }) {
  return (
    <section className="admin-panel">
      <h1>{title}</h1>
      <p className="admin-muted">{message}</p>
    </section>
  );
}

export default function NovelWorkspaceLayout({ message, setMessage }) {
  const { novelId } = useParams();
  const navigate = useNavigate();
  const [books, setBooks] = React.useState([]);
  const [chapters, setChapters] = React.useState([]);
  const [chapterBookFilter, setChapterBookFilter] = React.useState(null);
  const [extractedData, setExtractedData] = React.useState(null);
  const [extractionRuns, setExtractionRuns] = React.useState([]);
  const [extractingChapterId, setExtractingChapterId] = React.useState(null);
  const [isRunningExtraction, setIsRunningExtraction] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isNovelSettingsOpen, setIsNovelSettingsOpen] = React.useState(false);
  const [novel, setNovel] = React.useState(null);

  function recordsForChapter(reviewData, chapterId) {
    const reviewKeys = [
      "characters",
      "character_metadata_proposals",
      "progression_events",
      "character_skills",
      "skills",
      "items",
      "character_items",
      "life_events",
      "events",
    ];

    return reviewKeys.flatMap((key) =>
      (reviewData?.[key] || []).map((record) => ({ ...record, review_entity_type: key }))
    ).filter((record) => (record.source_chapter?.id || record.chapter?.id) === chapterId);
  }

  function enrichChapters(chapterRows, reviewData) {
    return chapterRows.map((chapter) => {
      const reviewRecords = recordsForChapter(reviewData, chapter.id);
      const pendingReviewCount = reviewRecords.filter((record) => record.review_status === "pending").length;
      const warningCount = reviewRecords.filter((record) => (record.review_warnings || []).length > 0).length;

      return {
        ...chapter,
        pending_review_count: pendingReviewCount,
        warning_count: warningCount,
      };
    });
  }

  async function loadWorkspace({ showLoading = true } = {}) {
    if (showLoading) {
      setIsLoading(true);
    }

    try {
      const [bookData, chapterData, reviewData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books`),
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters`),
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extracted-data`),
      ]);
      const runData = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extraction-runs`);
      setNovel(bookData.novel);
      setBooks(bookData.books || []);
      setExtractedData(reviewData);
      setExtractionRuns(runData.runs || []);
      setChapters(enrichChapters(chapterData.chapters || [], reviewData));
    } catch (error) {
      setMessage(error.message);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  async function loadExtractionRuns() {
    const runData = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extraction-runs`);
    const runs = runData.runs || [];
    setExtractionRuns(runs);
    setIsRunningExtraction(runs.some((run) => ["queued", "running"].includes(run.status)));
    return runs;
  }

  async function uploadBook(formData) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books/upload`, {
        method: "POST",
        body: formData,
      });
      await loadWorkspace();
      return data;
    } catch (error) {
      throw error;
    }
  }

  async function updateNovel(novelId, payload) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setNovel(data.novel);
      setIsNovelSettingsOpen(false);
      await loadWorkspace({ showLoading: false });
      return data.novel;
    } catch (error) {
      setMessage(error.message);
      return null;
    }
  }

  async function updateBook(bookId, payload) {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books/${bookId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadWorkspace();
    return data;
  }

  async function replaceBookSource(bookId, formData) {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books/${bookId}/source`, {
      method: "POST",
      body: formData,
    });
    await loadWorkspace();
    return data;
  }

  async function reparseBook(bookId) {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books/${bookId}/reparse`, {
      method: "POST",
    });
    await loadWorkspace();
    return data;
  }

  async function extractChapter(chapter) {
    setExtractingChapterId(chapter.id);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extraction-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope_type: "single_chapter",
          chapter_id: chapter.id,
        }),
      });
      setExtractionRuns((runs) => [data.run, ...runs.filter((run) => run.id !== data.run.id)]);
      setIsRunningExtraction(true);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setExtractingChapterId(null);
    }
  }

  async function startExtractionRun(payload) {
    setIsRunningExtraction(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extraction-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setExtractionRuns((runs) => [data.run, ...runs.filter((run) => run.id !== data.run.id)]);
    } catch (error) {
      await loadWorkspace({ showLoading: false });
      throw error;
    } finally {
      await loadExtractionRuns();
    }
  }

  async function stopExtractionRun(run) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extraction-runs/${run.id}/cancel`, {
        method: "POST",
      });
      setExtractionRuns((runs) => runs.map((existingRun) => existingRun.id === data.run.id ? data.run : existingRun));
      await loadExtractionRuns();
    } catch (error) {
      setMessage(error.message);
    }
  }

  function openBookChapters(book) {
    setChapterBookFilter(book.id);
    navigate(`/admin/novels/${novelId}/chapters`);
  }

  function openReviewForChapter() {
    navigate(`/admin/novels/${novelId}/review`);
  }

  React.useEffect(() => {
    loadWorkspace();
  }, [novelId]);

  React.useEffect(() => {
    const hasActiveRun = extractionRuns.some((run) => ["queued", "running"].includes(run.status));

    if (!hasActiveRun && !isRunningExtraction) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const runs = await loadExtractionRuns();
        const stillActive = runs.some((run) => ["queued", "running"].includes(run.status));

        if (!stillActive) {
          await loadWorkspace({ showLoading: false });
        }
      } catch (error) {
        setMessage(error.message);
      }
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [extractionRuns, isRunningExtraction, novelId]);

  if (isLoading) {
    return (
      <main className="workspace-shell single-sidebar">
        <WorkspaceSidebar novel={novel} />
        <section className="workspace-main">
          {message ? <div className="admin-message">{message}</div> : null}
          <EmptyState title="Loading workspace" message="Fetching novel books and review data." />
        </section>
      </main>
    );
  }

  return (
    <main className="workspace-shell single-sidebar">
      <WorkspaceSidebar novel={novel} />
      <section className="workspace-main">
        {message ? <div className="admin-message">{message}</div> : null}
        <Routes>
          <Route
            index
            element={
              <NovelWorkspaceOverview
                books={books}
                extractedData={extractedData}
                extractionRuns={extractionRuns}
                novel={novel}
                onOpenNovelSettings={() => setIsNovelSettingsOpen(true)}
              />
            }
          />
          <Route
            path="books"
            element={
              <BooksPage
                books={books}
                novel={novel}
                onOpenChapters={openBookChapters}
                onUploadBook={uploadBook}
                onUpdateBook={updateBook}
                onReplaceBookSource={replaceBookSource}
                onReparseBook={reparseBook}
              />
            }
          />
          <Route
            path="chapters"
            element={
              <ChaptersPage
                books={books}
                chapters={chapters}
                extractingChapterId={extractingChapterId}
                initialBookId={chapterBookFilter}
                onExtractChapter={extractChapter}
                onOpenReview={openReviewForChapter}
              />
            }
          />
          <Route
            path="extraction"
            element={
              <ExtractionPage
                books={books}
                chapters={chapters}
                extractionRuns={extractionRuns}
                isRunningExtraction={isRunningExtraction}
                novel={novel}
                onStartExtraction={startExtractionRun}
                onStopExtraction={stopExtractionRun}
              />
            }
          />
          <Route
            path="review"
            element={<WorkspacePlaceholder title="Review Queue" message="Book and chapter grouped review arrives in Phase 5." />}
          />
          <Route path="*" element={<WorkspacePlaceholder title="Workspace Section" message="This section is not implemented yet." />} />
        </Routes>
        {isNovelSettingsOpen && novel ? (
          <EditNovelModal
            novel={novel}
            onClose={() => setIsNovelSettingsOpen(false)}
            onSave={updateNovel}
          />
        ) : null}
      </section>
    </main>
  );
}
