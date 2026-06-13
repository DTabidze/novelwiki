import React from "react";
import { NavLink } from "react-router-dom";
import {
  ArrowLeft,
  BookMarked,
  BookOpen,
  ClipboardCheck,
  DatabaseZap,
  Files,
  History,
  LayoutDashboard,
  ScanSearch,
  Settings,
  TriangleAlert,
} from "lucide-react";

const workspaceGroups = [
  [
    "Core",
    [
      { label: "Overview", path: "", icon: LayoutDashboard },
      { label: "Books", path: "books", icon: BookOpen },
      { label: "Chapters", path: "chapters", icon: Files },
      { label: "Extraction", path: "extraction", icon: ScanSearch },
      { label: "Review Queue", path: "review", icon: ClipboardCheck },
    ],
  ],
  [
    "Wiki Data",
    [
      { label: "Editor", path: "editor", icon: DatabaseZap },
      { label: "Edit Log", path: "edit-log", icon: History },
    ],
  ],
  [
    "System",
    [
      { label: "Warnings", path: "warnings", icon: TriangleAlert },
      { label: "Settings", path: "settings", icon: Settings },
    ],
  ],
];

export default function WorkspaceSidebar({ novel }) {
  return (
    <aside className="workspace-sidebar">
      <div className="workspace-novel-switcher">
        {novel?.cover_image_url ? (
          <img className="admin-cover-small" src={novel.cover_image_url} alt="" />
        ) : (
          <div className="admin-cover-small">
            <BookMarked aria-hidden="true" size={18} strokeWidth={1.9} />
          </div>
        )}
        <div>
          <span>Novel Workspace</span>
          <strong title={novel?.title || "Loading..."}>{novel?.title || "Loading..."}</strong>
        </div>
      </div>

      <nav className="workspace-nav">
        <NavLink className="workspace-back-link" to="/admin/novels">
          <span>
            <ArrowLeft aria-hidden="true" size={17} strokeWidth={1.9} />
          </span>
          Back to Novels
        </NavLink>
        {workspaceGroups.map(([groupLabel, links]) => (
          <div className="workspace-nav-group" key={groupLabel}>
            <small>{groupLabel}</small>
            {links.map(({ label, path, icon: Icon }) => (
              <NavLink end={path === ""} key={label} to={path || "."}>
                <span>
                  <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
                </span>
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="workspace-tip-card">
        <strong>Workspace Tips</strong>
        <p>Books, chapters, extraction, and review all live inside the selected novel.</p>
      </div>
    </aside>
  );
}
