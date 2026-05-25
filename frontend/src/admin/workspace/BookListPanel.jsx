import React from "react";
import StatusBadge from "../components/StatusBadge.jsx";

export default function BookListPanel({ books }) {
  return (
    <section className="admin-panel">
      <div className="admin-section-header">
        <h2>Books</h2>
        <span>{books.length} total</span>
      </div>

      <div className="admin-table">
        <div className="admin-table-row admin-table-head">
          <span>Book</span>
          <span>Title</span>
          <span>Chapters</span>
          <span>Status</span>
        </div>
        {books.map((book) => (
          <div className="admin-table-row" key={book.id}>
            <span>Book {book.number}</span>
            <strong>{book.title}</strong>
            <span>{book.chapter_count || 0}</span>
            <StatusBadge tone={book.parsing_status === "parsed" ? "success" : "neutral"}>
              {book.parsing_status}
            </StatusBadge>
          </div>
        ))}
        {books.length === 0 ? <p className="admin-muted">No books uploaded yet.</p> : null}
      </div>
    </section>
  );
}
