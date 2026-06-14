import React from "react";
import { NavLink } from "react-router-dom";
import { BookOpen, FileText, LayoutDashboard, LogOut, Settings, Users } from "lucide-react";
import { useAuth } from "../../auth/AuthContext.jsx";

const globalLinks = [
  { label: "Dashboard", path: "/admin", icon: LayoutDashboard },
  { label: "Novels", path: "/admin/novels", icon: BookOpen },
  { label: "Users", path: "/admin/users", icon: Users },
  { label: "System Logs", path: "/admin/system-logs", icon: FileText },
  { label: "Settings", path: "/admin/settings", icon: Settings },
];

export default function AdminSidebar({ currentUser }) {
  const { isSuperadmin, logout } = useAuth();
  const visibleSystemLinks = isSuperadmin ? globalLinks.slice(2) : [];
  const initials = (currentUser?.username || "Admin").slice(0, 1).toUpperCase();

  return (
    <aside className="admin-sidebar">
      <div className="admin-brand">
        <div className="admin-brand-mark">NW</div>
        <div>
          <strong>Novel Wiki Admin</strong>
          <span>Editorial workspace</span>
        </div>
      </div>

      <nav className="admin-nav">
        <small>Main</small>
        {globalLinks.slice(0, 2).map(({ label, path, icon: Icon }) => (
          <NavLink end={path === "/admin"} key={path} to={path}>
            <span>
              <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
            </span>
            {label}
          </NavLink>
        ))}

        <small>System</small>
        {visibleSystemLinks.map(({ label, path, icon: Icon }) => (
          <NavLink key={path} to={path}>
            <span>
              <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
            </span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="admin-user-card">
        <div className="admin-user-avatar">{initials}</div>
        <div>
          <strong>{currentUser?.username || "Admin"}</strong>
          <span>{currentUser?.role === "superadmin" ? "Super Administrator" : "Editor"}</span>
        </div>
        <button className="admin-user-logout" type="button" onClick={logout} aria-label="Log out">
          <LogOut aria-hidden="true" size={16} strokeWidth={1.9} />
        </button>
      </div>
    </aside>
  );
}
