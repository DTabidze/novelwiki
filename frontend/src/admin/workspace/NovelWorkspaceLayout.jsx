import React from "react";
import { Routes, Route, useParams } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../../api.js";
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
  const [books, setBooks] = React.useState([]);
  const [extractedData, setExtractedData] = React.useState(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [novel, setNovel] = React.useState(null);

  async function loadWorkspace() {
    setIsLoading(true);

    try {
      const [bookData, reviewData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/books`),
        fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extracted-data`),
      ]);
      setNovel(bookData.novel);
      setBooks(bookData.books || []);
      setExtractedData(reviewData);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsLoading(false);
    }
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
            element={<WorkspacePlaceholder title="Books" message="Book upload and table arrive in Phase 3." />}
          />
          <Route
            path="chapters"
            element={<WorkspacePlaceholder title="Chapters" message="Book-grouped chapter inspection arrives in Phase 3." />}
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
