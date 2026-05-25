import React from "react";

export default function BookUploadModal({ nextNumber, onClose, onUpload }) {
  const [file, setFile] = React.useState(null);
  const [number, setNumber] = React.useState(String(nextNumber || 1));
  const [title, setTitle] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("number", number);
    formData.append("title", title);
    setIsUploading(true);

    try {
      await onUpload(formData);
      setFile(null);
      setTitle("");
      setNumber(String(nextNumber || 1));
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
          <button className="admin-icon-button" type="button" onClick={onClose}>
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
              onChange={(event) => setNumber(event.target.value)}
            />
          </label>
          <label>
            Book title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={`Book ${nextNumber || 1}`}
            />
          </label>
        </div>

        <label>
          Text file
          <input
            accept=".txt,text/plain"
            type="file"
            onChange={(event) => setFile(event.target.files[0])}
          />
        </label>

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={!file || isUploading} type="submit">
            {isUploading ? "Uploading..." : "Upload Book"}
          </button>
        </div>
      </form>
    </div>
  );
}
