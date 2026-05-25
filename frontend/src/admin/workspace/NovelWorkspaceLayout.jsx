import React from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../../api.js";
import BooksPage from "../books/BooksPage.jsx";
import ChaptersPage from "../chapters/ChaptersPage.jsx";
import EmptyState from "../components/EmptyState.jsx";
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
  const [extractingChapterId, setExtractingChapterId] = React.useState(null);
  const [isLoading, setIsLoading] = React.useState(true);
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

  async function loadWorkspace() {
    setIsLoading(true);

    try {
      const [bookData, chapterData, reviewData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books`),
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters`),
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extracted-data`),
      ]);
      setNovel(bookData.novel);
      setBooks(bookData.books || []);
      setExtractedData(reviewData);
      setChapters(enrichChapters(chapterData.chapters || [], reviewData));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function uploadBook(formData) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books/upload`, {
        method: "POST",
        body: formData,
      });
      setMessage(`Uploaded ${data.book.title} with ${data.chapter_count} chapters.`);
      await loadWorkspace();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function extractChapter(chapter) {
    setExtractingChapterId(chapter.id);
    setMessage(`Extracting Chapter ${chapter.chapter_number}...`);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters/${chapter.id}/extract`, {
        method: "POST",
      });
      setExtractedData(data);
      setMessage(`Chapter ${chapter.chapter_number} extracted. Review pending records when ready.`);
      await loadWorkspace();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setExtractingChapterId(null);
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
          <Route index element={<NovelWorkspaceOverview books={books} extractedData={extractedData} novel={novel} />} />
          <Route
            path="books"
            element={
              <BooksPage
                books={books}
                novel={novel}
                onOpenChapters={openBookChapters}
                onUploadBook={uploadBook}
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
            element={<WorkspacePlaceholder title="Extraction" message="Scoped extraction runs arrive in Phase 4." />}
          />
          <Route
            path="review"
            element={<WorkspacePlaceholder title="Review Queue" message="Book and chapter grouped review arrives in Phase 5." />}
          />
          <Route path="*" element={<WorkspacePlaceholder title="Workspace Section" message="This section is not implemented yet." />} />
        </Routes>
      </section>
    </main>
  );
}
