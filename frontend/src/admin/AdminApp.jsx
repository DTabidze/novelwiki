import React from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../api.js";
import AdminLayout from "./components/AdminLayout.jsx";
import AdminSidebar from "./components/AdminSidebar.jsx";
import EmptyState from "./components/EmptyState.jsx";
import NovelLibraryPage from "./novels/NovelLibraryPage.jsx";
import NovelWorkspaceLayout from "./workspace/NovelWorkspaceLayout.jsx";

function AdminPlaceholder({ title }) {
  return (
    <EmptyState
      title={title}
      message="This global admin section is reserved for a later phase."
    />
  );
}

export default function AdminApp() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [novels, setNovels] = React.useState([]);

  async function loadNovels() {
    setIsLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels`);
      setNovels(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreateNovel(payload) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      await loadNovels();
      setMessage(`Created ${data.novel.title}.`);
      return data.novel;
    } catch (error) {
      setMessage(error.message);
      return null;
    }
  }

  function handleOpenNovel(novel) {
    navigate(`/admin/novels/${novel.id}`);
  }

  React.useEffect(() => {
    loadNovels();
  }, []);

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin/novels" replace />} />
      <Route
        path="/novels"
        element={
          <AdminLayout message={message} sidebar={<AdminSidebar />}>
            <NovelLibraryPage
              loading={isLoading}
              novels={novels}
              onCreateNovel={handleCreateNovel}
              onOpenNovel={handleOpenNovel}
            />
          </AdminLayout>
        }
      />
      <Route path="/novels/:novelId/*" element={<NovelWorkspaceLayout message={message} setMessage={setMessage} />} />
      <Route
        path="/users"
        element={
          <AdminLayout message={message} sidebar={<AdminSidebar />}>
            <AdminPlaceholder title="Users" />
          </AdminLayout>
        }
      />
      <Route
        path="/system-logs"
        element={
          <AdminLayout message={message} sidebar={<AdminSidebar />}>
            <AdminPlaceholder title="System Logs" />
          </AdminLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <AdminLayout message={message} sidebar={<AdminSidebar />}>
            <AdminPlaceholder title="Settings" />
          </AdminLayout>
        }
      />
    </Routes>
  );
}
