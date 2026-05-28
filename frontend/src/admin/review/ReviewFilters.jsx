import React from "react";
import { Search } from "lucide-react";

export default function ReviewFilters({ books, filters, onChange }) {
  function update(key, value) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="review-filter-bar">
      <label>
        Book
        <select value={filters.bookId} onChange={(event) => update("bookId", event.target.value)}>
          <option value="all">All books</option>
          {books.map((book) => (
            <option key={book.id} value={book.id}>
              Book {book.number}: {book.title}
            </option>
          ))}
        </select>
      </label>

      <label>
        Chapter Range
        <input
          value={filters.chapterRange}
          onChange={(event) => update("chapterRange", event.target.value)}
          placeholder="Any"
        />
      </label>

      <label>
        Type
        <select value={filters.typeGroup} onChange={(event) => update("typeGroup", event.target.value)}>
          <option value="all">All types</option>
          <option value="characters">Characters</option>
          <option value="metadata">Metadata</option>
          <option value="progression">Progression</option>
          <option value="skills_items">Skills & Items</option>
        </select>
      </label>

      <label>
        Status
        <select value={filters.status} onChange={(event) => update("status", event.target.value)}>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All statuses</option>
        </select>
      </label>

      <label className="review-toggle-row">
        <span>Warnings Only</span>
        <input
          type="checkbox"
          checked={filters.warningsOnly}
          onChange={(event) => update("warningsOnly", event.target.checked)}
        />
      </label>

      <label className="review-search-field">
        <Search aria-hidden="true" size={16} strokeWidth={1.9} />
        <input
          value={filters.search}
          onChange={(event) => update("search", event.target.value)}
          placeholder="Search in results..."
        />
      </label>
    </section>
  );
}
