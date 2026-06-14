import React from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import LoginPage from "./auth/LoginPage.jsx";
import AdminLayout from "./components/AdminLayout.jsx";
import AdminSidebar from "./components/AdminSidebar.jsx";
import EmptyState from "./components/EmptyState.jsx";
import NovelLibraryPage from "./novels/NovelLibraryPage.jsx";
import UsersAccessPage from "./users/UsersAccessPage.jsx";
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
  const { currentUser, isAuthLoading, isSuperadmin } = useAuth();
  const location = useLocation();
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      await loadNovels();
      return data.novel;
    } catch (error) {
      setMessage(error.message);
      return null;
    }
  }

  async function handleUpdateNovel(novelId, payload) {
    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      await loadNovels();
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
    if (currentUser?.role && currentUser.role !== "user") {
      loadNovels();
    }
  }, [currentUser?.id]);

  if (isAuthLoading) {
    return (
      <AdminLayout message="" sidebar={null}>
        <EmptyState title="Checking session" message="Loading your admin access." />
      </AdminLayout>
    );
  }

  if (location.pathname.endsWith("/login")) {
    return <LoginPage />;
  }

  if (!currentUser || currentUser.role === "user") {
    return <Navigate to="/admin/login" replace state={{ from: location }} />;
  }

  const sidebar = <AdminSidebar currentUser={currentUser} />;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Navigate to="/admin/novels" replace />} />
      <Route
        path="/novels"
        element={
          <AdminLayout message={message} sidebar={sidebar}>
            <NovelLibraryPage
              canCreateNovel={isSuperadmin}
              loading={isLoading}
              novels={novels}
              onCreateNovel={handleCreateNovel}
              onOpenNovel={handleOpenNovel}
              onUpdateNovel={handleUpdateNovel}
            />
          </AdminLayout>
        }
      />
      <Route path="/novels/:novelId/*" element={<NovelWorkspaceLayout currentUser={currentUser} message={message} setMessage={setMessage} />} />
      <Route
        path="/users"
        element={
          <AdminLayout message={message} sidebar={sidebar}>
            {isSuperadmin ? <UsersAccessPage /> : <Navigate to="/admin/novels" replace />}
          </AdminLayout>
        }
      />
      <Route
        path="/system-logs"
        element={
          <AdminLayout message={message} sidebar={sidebar}>
            {isSuperadmin ? <AdminPlaceholder title="System Logs" /> : <Navigate to="/admin/novels" replace />}
          </AdminLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <AdminLayout message={message} sidebar={sidebar}>
            {isSuperadmin ? <AdminPlaceholder title="Settings" /> : <Navigate to="/admin/novels" replace />}
          </AdminLayout>
        }
      />
    </Routes>
  );
}
