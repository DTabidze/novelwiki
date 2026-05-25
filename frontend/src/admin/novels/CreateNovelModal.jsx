import React from "react";

export default function CreateNovelModal({ onClose, onCreate }) {
  const [title, setTitle] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    setIsSaving(true);

    try {
      await onCreate({ title: title.trim() });
      setTitle("");
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
