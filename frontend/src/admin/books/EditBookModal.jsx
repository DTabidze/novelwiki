import React from "react";
import { X } from "lucide-react";

export default function EditBookModal({ book, books, onClose, onSave }) {
  const [number, setNumber] = React.useState(String(book.number || ""));
  const [title, setTitle] = React.useState(book.title || "");
  const [error, setError] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);

  const parsedNumber = Number(number);
  const duplicateBook = books.find(
    (existingBook) => existingBook.id !== book.id && existingBook.number === parsedNumber
  );
  const validationError = duplicateBook ? `Book ${parsedNumber} already exists.` : "";

  async function handleSubmit(event) {
    event.preventDefault();

    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSaving(true);
    setError("");

    try {
      await onSave(book, { number, title });
    } catch (saveError) {
      setError(saveError.message || "Could not update this book.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={handleSubmit}>
        <div className="admin-modal-header">
          <div>
            <h2>Edit Book</h2>
            <p>Safely update book metadata. Source files and chapters are not changed.</p>
          </div>
          <button className="admin-icon-button modal-close-button" disabled={isSaving} type="button" onClick={onClose} aria-label="Close">
            <X aria-hidden="true" size={16} />
          </button>
        </div>

        <div className="book-upload-grid">
          <label>
            Book number
            <input
              min="1"
              type="number"
              value={number}
              disabled={isSaving}
              onChange={(event) => {
                setNumber(event.target.value);
                setError("");
              }}
            />
          </label>
          <label>
            Book title
            <input
              value={title}
              disabled={isSaving}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={`Book ${number || book.number}`}
            />
          </label>
        </div>

        {validationError || error ? (
          <div className="admin-inline-error">{error || validationError}</div>
        ) : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" disabled={isSaving} type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={isSaving || Boolean(validationError)} type="submit">
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
