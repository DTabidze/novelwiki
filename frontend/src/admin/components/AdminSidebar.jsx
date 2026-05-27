import React from "react";
import { NavLink } from "react-router-dom";

const globalLinks = [
  ["Dashboard", "/admin"],
  ["Novels", "/admin/novels"],
  ["Users", "/admin/users"],
  ["System Logs", "/admin/system-logs"],
  ["Settings", "/admin/settings"],
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
        {globalLinks.slice(0, 2).map(([label, path]) => (
          <NavLink end={path === "/admin"} key={path} to={path}>
            <span>{label.slice(0, 1)}</span>
            {label}
          </NavLink>
        ))}

        <small>System</small>
        {globalLinks.slice(2).map(([label, path]) => (
          <NavLink key={path} to={path}>
            <span>{label.slice(0, 1)}</span>
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
