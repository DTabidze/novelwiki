import React from "react";

export default function ReplaceBookSourceModal({ book, onClose, onReplace }) {
  const [file, setFile] = React.useState(null);
  const [error, setError] = React.useState("");
  const [isReplacing, setIsReplacing] = React.useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      setError("Please select a source file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setIsReplacing(true);
    setError("");

    try {
      await onReplace(book, formData);
    } catch (replaceError) {
      setError(replaceError.message || "Could not replace this source file.");
    } finally {
      setIsReplacing(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={handleSubmit}>
        <div className="admin-modal-header">
          <div>
            <h2>Replace Source File</h2>
            <p>This stores a new source file for Book {book.number} and clears its current parsed chapters.</p>
          </div>
          <button className="admin-icon-button" disabled={isReplacing} type="button" onClick={onClose}>
            X
          </button>
        </div>

        <label>
          Source file
          <input
            accept=".txt,text/plain"
            disabled={isReplacing}
            type="file"
            onChange={(event) => {
              setFile(event.target.files[0]);
              setError("");
            }}
          />
        </label>

        <div className="book-modal-note">
          Current source: <strong>{book.source_filename || "No source file"}</strong>
          <br />
          Reparse this book after replacement to recreate chapters from the new file.
        </div>

        {error ? <div className="admin-inline-error">{error}</div> : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" disabled={isReplacing} type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={!file || isReplacing} type="submit">
            {isReplacing ? "Replacing..." : "Replace Source"}
          </button>
        </div>
      </form>
    </div>
  );
}
