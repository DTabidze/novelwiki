import React from "react";
import { NavLink } from "react-router-dom";

const workspaceGroups = [
  [
    "Core",
    [
      ["Overview", ""],
      ["Books", "books"],
      ["Chapters", "chapters"],
      ["Extraction", "extraction"],
      ["Review Queue", "review"],
    ],
  ],
  [
    "Wiki Data",
    [
      ["Characters", "characters"],
      ["Skills", "skills"],
      ["Items", "items"],
      ["Progression", "progression"],
    ],
  ],
  [
    "System",
    [
      ["Warnings", "warnings"],
      ["Settings", "settings"],
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
          <div className="admin-cover-small">{novel?.title?.slice(0, 2) || "NW"}</div>
        )}
        <div>
          <span>Novel Workspace</span>
          <strong title={novel?.title || "Loading..."}>{novel?.title || "Loading..."}</strong>
        </div>
      </div>

      <nav className="workspace-nav">
        <NavLink className="workspace-back-link" to="/admin/novels">
          <span>B</span>
          Back to Novels
        </NavLink>
        {workspaceGroups.map(([groupLabel, links]) => (
          <div className="workspace-nav-group" key={groupLabel}>
            <small>{groupLabel}</small>
            {links.map(([label, path]) => (
              <NavLink end={path === ""} key={label} to={path || "."}>
                <span>{label.slice(0, 1)}</span>
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
