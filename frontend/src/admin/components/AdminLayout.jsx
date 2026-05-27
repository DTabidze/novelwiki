import React from "react";
import AdminSidebar from "./AdminSidebar.jsx";

export default function AdminLayout({ children, message, sidebar = <AdminSidebar /> }) {
  return (
    <main className="admin-shell">
      {sidebar}
      <section className="admin-main">
        {message ? <div className="admin-message">{message}</div> : null}
        {children}
      </section>
    </main>
  );
}
