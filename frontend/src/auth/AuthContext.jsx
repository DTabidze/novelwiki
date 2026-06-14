import React from "react";
import { API_BASE_URL, fetchJson, setCsrfToken } from "../api.js";

const AuthContext = React.createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = React.useState(null);
  const [isAuthLoading, setIsAuthLoading] = React.useState(true);

  async function refreshCurrentUser() {
    setIsAuthLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/auth/me`);
      setCsrfToken(data.csrf_token || data.user?.csrf_token);
      setCurrentUser(data.user || null);
      return data.user || null;
    } finally {
      setIsAuthLoading(false);
    }
  }

  async function login(email, password) {
    const data = await fetchJson(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setCsrfToken(data.user?.csrf_token);
    setCurrentUser(data.user);
    return data.user;
  }

  async function logout() {
    await fetchJson(`${API_BASE_URL}/auth/logout`, { method: "POST" });
    setCsrfToken(null);
    setCurrentUser(null);
  }

  React.useEffect(() => {
    refreshCurrentUser().catch(() => {
      setCurrentUser(null);
      setIsAuthLoading(false);
    });
  }, []);

  const value = React.useMemo(
    () => ({
      currentUser,
      isAuthLoading,
      isSuperadmin: currentUser?.role === "superadmin",
      isEditor: currentUser?.role === "editor",
      login,
      logout,
      refreshCurrentUser,
    }),
    [currentUser, isAuthLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = React.useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
