import React from "react";
import { X } from "lucide-react";

export default function CreateNovelModal({ onClose, onCreate }) {
  const [title, setTitle] = React.useState("");
  const [author, setAuthor] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [coverImageUrl, setCoverImageUrl] = React.useState("");
  const [status, setStatus] = React.useState("ready");
  const [isSaving, setIsSaving] = React.useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    setIsSaving(true);

    try {
      await onCreate({
        title: title.trim(),
        author: author.trim(),
        description: description.trim(),
        cover_image_url: coverImageUrl.trim(),
        status,
      });
      setTitle("");
      setAuthor("");
      setDescription("");
      setCoverImageUrl("");
      setStatus("ready");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={handleSubmit}>
        <div className="admin-modal-header">
          <div>
            <h2>Create Novel</h2>
            <p>Create an empty workspace. Books are uploaded inside the novel workspace.</p>
          </div>
          <button className="admin-icon-button modal-close-button" type="button" onClick={onClose} aria-label="Close">
            <X aria-hidden="true" size={16} />
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

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={!title.trim() || isSaving} type="submit">
            {isSaving ? "Creating..." : "Create Novel"}
          </button>
        </div>
      </form>
    </div>
  );
}
