import React from "react";
import StatusBadge from "../components/StatusBadge.jsx";

export default function BookListPanel({ books }) {
  return (
    <section className="admin-panel workspace-book-panel">
      <div className="admin-section-header">
        <h2>Books</h2>
        <span>{books.length} total</span>
      </div>

      <div className="admin-table">
        <div className="admin-table-row admin-table-head">
          <span>Book</span>
          <span>Title</span>
          <span>Chapters</span>
          <span>Extracted</span>
          <span>Status</span>
        </div>
        {books.map((book) => (
          <div className="admin-table-row" key={book.id}>
            <span>Book {book.number}</span>
            <strong>{book.title}</strong>
            <span>{book.chapter_count || 0}</span>
            <span>{book.extracted_chapter_count || 0}</span>
            <StatusBadge tone={book.extraction_status === "completed" ? "success" : "neutral"}>
              {book.extraction_status}
            </StatusBadge>
          </div>
        ))}
        {books.length === 0 ? <p className="admin-muted">No books uploaded yet.</p> : null}
      </div>
    </section>
  );
}
