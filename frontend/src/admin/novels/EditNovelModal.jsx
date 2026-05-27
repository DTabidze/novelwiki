import React from "react";

export default function EditNovelModal({ novel, onClose, onSave }) {
  const [title, setTitle] = React.useState(novel?.title || "");
  const [author, setAuthor] = React.useState(novel?.author || "");
  const [description, setDescription] = React.useState(novel?.description || "");
  const [coverImageUrl, setCoverImageUrl] = React.useState(novel?.cover_image_url || "");
  const [status, setStatus] = React.useState(novel?.status || "ready");
  const [isSaving, setIsSaving] = React.useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    setIsSaving(true);

    try {
      await onSave(novel.id, {
        title: title.trim(),
        author: author.trim(),
        description: description.trim(),
        cover_image_url: coverImageUrl.trim(),
        status,
      });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={handleSubmit}>
        <div className="admin-modal-header">
          <div>
            <h2>Edit Novel</h2>
            <p>Update workspace profile information. Books and extracted records are unchanged.</p>
          </div>
          <button className="admin-icon-button" type="button" onClick={onClose}>
            X
          </button>
        </div>

        <label>
          Novel title
          <input
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="I Shall Seal the Heavens"
          />
        </label>

        <label>
          Author
          <input
            value={author}
            onChange={(event) => setAuthor(event.target.value)}
            placeholder="Er Gen"
          />
        </label>

        <label>
          Description
          <textarea
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Short workspace/public wiki description"
          />
        </label>

        <label>
          Cover image URL
          <input
            value={coverImageUrl}
            onChange={(event) => setCoverImageUrl(event.target.value)}
            placeholder="https://example.com/cover.jpg"
          />
        </label>

        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="ready">Ready</option>
            <option value="draft">Draft</option>
          </select>
        </label>

        <section className="admin-danger-zone">
          <div>
            <h3>Delete Novel</h3>
            <p>Deletion behavior is not enabled yet. We will decide later how books and extracted data should be handled.</p>
          </div>
          <button className="admin-danger-button" disabled type="button">
            Delete Novel
          </button>
        </section>

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={!title.trim() || isSaving} type="submit">
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
