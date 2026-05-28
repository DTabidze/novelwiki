import React from "react";

export default function ReviewBookList({ books, countsByBook, selectedBookId, onSelectBook }) {
  return (
    <aside className="review-books-panel admin-panel">
      <div className="review-panel-title">
        <h2>Books</h2>
      </div>

      <div className="review-book-list">
        <button
          type="button"
          className={selectedBookId === "all" ? "review-book-row active" : "review-book-row"}
          onClick={() => onSelectBook("all")}
        >
          <strong>All books</strong>
          <span>{countsByBook.all || 0} pending</span>
        </button>

        {books.map((book) => {
          const count = countsByBook[book.id] || 0;

          return (
            <button
              type="button"
              key={book.id}
              className={String(selectedBookId) === String(book.id) ? "review-book-row active" : "review-book-row"}
              onClick={() => onSelectBook(String(book.id))}
            >
              <strong>Book {book.number}</strong>
              <small title={book.title}>{book.title}</small>
              <span>{count} pending</span>
            </button>
          );
        })}
      </div>

      <button type="button" className="admin-secondary-button review-completed-button">
        Show Completed Books
      </button>
    </aside>
  );
}
