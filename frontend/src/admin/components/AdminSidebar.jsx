import React from "react";
import { NavLink } from "react-router-dom";
import { FileText, LayoutDashboard, Settings, Users, BookOpen } from "lucide-react";

const globalLinks = [
  { label: "Dashboard", path: "/admin", icon: LayoutDashboard },
  { label: "Novels", path: "/admin/novels", icon: BookOpen },
  { label: "Users", path: "/admin/users", icon: Users },
  { label: "System Logs", path: "/admin/system-logs", icon: FileText },
  { label: "Settings", path: "/admin/settings", icon: Settings },
];

export default function AdminSidebar() {
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
        {globalLinks.slice(2).map(({ label, path, icon: Icon }) => (
          <NavLink key={path} to={path}>
            <span>
              <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
            </span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="admin-user-card">
        <div className="admin-user-avatar">A</div>
        <div>
          <strong>Admin</strong>
          <span>Super Administrator</span>
        </div>
      </div>
    </aside>
  );
}
