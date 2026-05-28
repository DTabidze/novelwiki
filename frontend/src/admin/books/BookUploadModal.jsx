import React from "react";

export default function BookUploadModal({ nextNumber, onClose, onUpload }) {
  const [file, setFile] = React.useState(null);
  const [number, setNumber] = React.useState(String(nextNumber || 1));
  const [title, setTitle] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState("");
  const filenameWarning = getFilenameBookWarning(file?.name, number);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      setError("Upload failed. Please select a valid .txt file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("number", number);
    formData.append("title", title);
    setIsUploading(true);
    setError("");

    try {
      await onUpload(formData);
      setFile(null);
      setTitle("");
      setNumber(String(nextNumber || 1));
    } catch (uploadError) {
      setError(`Upload failed. ${uploadError.message || "Please try again."}`);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={handleSubmit}>
        <div className="admin-modal-header">
          <div>
            <h2>Upload Book</h2>
            <p>Add a source text file to this novel workspace.</p>
          </div>
          <button className="admin-icon-button" disabled={isUploading} type="button" onClick={onClose}>
            X
          </button>
        </div>

        <div className="book-upload-grid">
          <label>
            Book number
            <input
              min="1"
              type="number"
              value={number}
              disabled={isUploading}
              onChange={(event) => setNumber(event.target.value)}
            />
          </label>
          <label>
            Book title
            <input
              value={title}
              disabled={isUploading}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={`Book ${nextNumber || 1}`}
            />
          </label>
        </div>

        <label>
          Text file
          <input
            accept=".txt,text/plain"
            disabled={isUploading}
            type="file"
            onChange={(event) => {
              setFile(event.target.files[0]);
              setError("");
            }}
          />
        </label>

        {error ? <div className="admin-inline-error">{error}</div> : null}
        {filenameWarning ? <div className="admin-inline-warning">{filenameWarning}</div> : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" disabled={isUploading} type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={!file || isUploading} type="submit">
            {isUploading ? "Parsing..." : "Upload Book"}
          </button>
        </div>
      </form>
    </div>
  );
}

function getFilenameBookWarning(filename, bookNumber) {
  if (!filename || !bookNumber) {
    return "";
  }

  const selectedNumber = Number(bookNumber);

  if (!Number.isFinite(selectedNumber) || selectedNumber <= 0) {
    return "";
  }

  const normalized = filename.replace(/[_-]+/g, " ");
  const match = normalized.match(/\b(?:volume|vol|book)\s*0*(\d{1,4})\b/i);

  if (!match) {
    return "";
  }

  const filenameNumber = Number(match[1]);

  if (filenameNumber === selectedNumber) {
    return "";
  }

  return `Filename looks like Book ${filenameNumber}, but this upload is set to Book ${selectedNumber}. Check before uploading.`;
}
