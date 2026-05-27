import React from "react";
import StatusBadge from "../components/StatusBadge.jsx";

export default function BookTable({ books, onOpenChapters }) {
  return (
    <div className="admin-table book-table">
      <div className="admin-table-row admin-table-head">
        <span>Book</span>
        <span>Title</span>
        <span>Source</span>
        <span>Chapters</span>
        <span>Parsing</span>
        <span>Extraction</span>
        <span>Actions</span>
      </div>

      {books.map((book) => (
        <div className="admin-table-row" key={book.id}>
          <strong>Book {book.number}</strong>
          <span>{book.title}</span>
          <span className="admin-truncate" title={book.source_filename || ""}>
            {book.source_filename || "No file"}
          </span>
          <span>{book.chapter_count || 0}</span>
          <StatusBadge tone={book.parsing_status === "parsed" ? "success" : "neutral"}>
            {book.parsing_status}
          </StatusBadge>
          <StatusBadge tone={book.extraction_status === "completed" ? "success" : "neutral"}>
            {book.extraction_status}
          </StatusBadge>
          <button className="admin-secondary-button" type="button" onClick={() => onOpenChapters(book)}>
            Chapters
          </button>
        </div>
      ))}
    </div>
  );
}
