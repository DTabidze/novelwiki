import React from "react";

export default function ReparseBookModal({ book, onClose, onConfirm }) {
  const [isReparsing, setIsReparsing] = React.useState(false);
  const [error, setError] = React.useState("");

  async function handleConfirm() {
    setIsReparsing(true);
    setError("");

    try {
      await onConfirm(book);
    } catch (reparseError) {
      setError(reparseError.message || "Could not reparse this book.");
    } finally {
      setIsReparsing(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <section className="admin-modal">
        <div className="admin-modal-header">
          <div>
            <h2>Reparse Book</h2>
            <p>This is destructive and should only be used before review data exists.</p>
          </div>
          <button className="admin-icon-button" disabled={isReparsing} type="button" onClick={onClose}>
            X
          </button>
        </div>

        <div className="admin-danger-zone book-danger-stack">
          <div>
            <h3>Delete parsed chapters for Book {book.number}?</h3>
            <p>
              Reparse deletes the existing parsed chapters for this book and recreates them from the current source
              file. It may also invalidate related extracted or review data, so the backend blocks this action once
              linked data exists.
            </p>
          </div>
        </div>

        {error ? <div className="admin-inline-error">{error}</div> : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" disabled={isReparsing} type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="admin-danger-button" disabled={isReparsing} type="button" onClick={handleConfirm}>
            {isReparsing ? "Reparsing..." : "Reparse Book"}
          </button>
        </div>
      </section>
    </div>
  );
}
