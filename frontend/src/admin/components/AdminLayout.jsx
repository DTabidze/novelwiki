import React from "react";
import { Menu, X } from "lucide-react";
import { useAuth } from "../../auth/AuthContext.jsx";
import AdminSidebar from "./AdminSidebar.jsx";

export default function AdminLayout({ children, message, sidebar = <AdminSidebar /> }) {
  const { currentUser } = useAuth();
  const [isMobileNavOpen, setIsMobileNavOpen] = React.useState(false);
  const initials = (currentUser?.username || "Admin").slice(0, 1).toUpperCase();

  return (
    <main className="admin-shell">
      <header className="admin-mobile-topbar">
        <button
          className="admin-mobile-menu-button"
          type="button"
          aria-label="Open admin navigation"
          aria-expanded={isMobileNavOpen}
          onClick={() => setIsMobileNavOpen(true)}
        >
          <Menu aria-hidden="true" size={22} strokeWidth={1.9} />
        </button>
        <div className="admin-mobile-brand">
          <div>
            <strong>Novel Wiki Admin</strong>
            <span>Editorial workspace</span>
          </div>
        </div>
        <div className="admin-mobile-avatar">{initials}</div>
      </header>

      {isMobileNavOpen ? (
        <button
          className="admin-mobile-drawer-scrim"
          type="button"
          aria-label="Close admin navigation"
          onClick={() => setIsMobileNavOpen(false)}
        />
      ) : null}
      <div className={isMobileNavOpen ? "admin-mobile-drawer open" : "admin-mobile-drawer"}>
        <div className="admin-mobile-drawer-header">
          <div>
            <strong>Novel Wiki Admin</strong>
            <span>Editorial workspace</span>
          </div>
          <button
            className="admin-mobile-drawer-close"
            type="button"
            aria-label="Close admin navigation"
            onClick={() => setIsMobileNavOpen(false)}
          >
            <X aria-hidden="true" size={20} strokeWidth={1.9} />
          </button>
        </div>
        <div onClick={(event) => event.target.closest("a") && setIsMobileNavOpen(false)}>
          {sidebar}
        </div>
      </div>

      {sidebar}
      <section className="admin-main">
        {message ? <div className="admin-message">{message}</div> : null}
        {children}
      </section>
    </main>
  );
}
