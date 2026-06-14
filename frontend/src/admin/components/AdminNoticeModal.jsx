import React from "react";
import { TriangleAlert, X } from "lucide-react";

export default function AdminNoticeModal({ title = "Something went wrong", message, actionLabel, onAction, onClose }) {
  if (!message) {
    return null;
  }

  return (
    <div className="admin-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="admin-modal admin-notice-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-notice-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-modal-header">
          <div className="admin-notice-heading">
            <span className="admin-notice-icon danger">
              <TriangleAlert aria-hidden="true" size={18} strokeWidth={2} />
            </span>
            <div>
              <h2 id="admin-notice-title">{title}</h2>
              <p>{message}</p>
            </div>
          </div>
          <button className="admin-icon-button modal-close-button" type="button" onClick={onClose} aria-label="Close">
            <X aria-hidden="true" size={17} />
          </button>
        </div>
        {actionLabel && onAction ? (
          <footer className="admin-modal-actions">
            <button type="button" className="admin-primary-button" onClick={onAction}>
              {actionLabel}
            </button>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
