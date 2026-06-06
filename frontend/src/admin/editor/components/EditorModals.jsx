import React from "react";
import {
  CircleAlert,
  Info,
  Package,
  Pencil,
  Plus,
  Save,
  Sparkles,
  Star,
  Timeline,
  Trash2,
  Type,
  Users,
  X,
} from "lucide-react";

const CHANGE_GROUPS = [
  { id: "updated", label: "Updated" },
  { id: "added", label: "Added" },
  { id: "removed", label: "Removed" },
];

function ChangeTypeIcon({ change }) {
  if (change.entityType === "field") return <Type aria-hidden="true" size={19} />;
  if (change.entityType === "alias") return <Star aria-hidden="true" size={19} />;
  if (change.entityType === "skill") return <Sparkles aria-hidden="true" size={19} />;
  if (change.entityType === "item") return <Package aria-hidden="true" size={19} />;
  if (change.entityType === "character") return <Users aria-hidden="true" size={19} />;
  if (change.entityType === "cultivation breakthrough") return <Timeline aria-hidden="true" size={19} />;
  return <Pencil aria-hidden="true" size={19} />;
}

function groupChanges(changes = []) {
  return CHANGE_GROUPS.map((group) => ({
    ...group,
    changes: changes.filter((change) => change.operation === group.id),
  })).filter((group) => group.changes.length);
}

function ChangeReviewList({ changes, onEditChange, showEdit = true }) {
  const groupedChanges = groupChanges(changes);

  if (!groupedChanges.length) {
    return (
      <div className="editor-save-summary-box muted">
        <Info aria-hidden="true" size={16} />
        <span>Nothing has changed since this record was loaded.</span>
      </div>
    );
  }

  return groupedChanges.map(({ id, label: groupLabel, changes: groupChanges }) => (
    <section className={`editor-change-group ${id}`} key={id}>
      <h3>
        <span className="editor-change-group-dot" />
        {groupChanges.length} {groupLabel}
      </h3>
      <div className="editor-change-row-list">
        {groupChanges.map((change) => (
          <article className={`editor-change-row ${showEdit ? "" : "no-action"}`} key={change.id}>
            <span className="editor-change-icon-box">
              <ChangeTypeIcon change={change} />
            </span>
            <div className="editor-change-copy">
              <strong>{change.label}</strong>
              {change.operation === "updated" ? (
                <p>
                  <span className="editor-change-old">{change.oldValue}</span>
                  <span className="editor-change-arrow">→</span>
                  <span className="editor-change-new">{change.newValue}</span>
                </p>
              ) : (
                <p className={`editor-change-value ${change.operation}`}>{change.displayValue}</p>
              )}
            </div>
            {showEdit ? (
              <button type="button" className="editor-change-edit-button" onClick={() => onEditChange(change)}>
                <Pencil aria-hidden="true" size={15} />
                Edit
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  ));
}

export function EditorConfirmModal({ action, onCancel, onConfirm, onEditChange }) {
  if (!action) {
    return null;
  }

  const isSave = action.type === "save";
  const isAlias = action.type === "alias" || action.type === "skill_alias";
  const isSkill = action.type === "skill";
  const isSkillCharacter = action.type === "skill_character";
  const isItem = action.type === "item";
  const isItemCharacter = action.type === "item_character";
  const title = isSave ? "Save Wiki Data Changes?" : isAlias ? "Delete Alias?" : isSkill ? "Remove Skill?" : isItem ? "Remove Item?" : isSkillCharacter || isItemCharacter ? "Remove Character?" : "Delete Cultivation Record?";
  const label = isAlias
    ? action.draft?.alias || "this alias"
    : action.type === "cultivation"
      ? action.draft?.cultivation_level || "this cultivation breakthrough"
      : isSkill
        ? action.draft?.skill_name || "this skill relationship"
        : isItem
          ? action.draft?.item_name || "this item relationship"
          : isSkillCharacter || isItemCharacter
            ? action.draft?.character_name || "this character relationship"
            : action.draft?.name || "this character";
  const message = isSave
    ? "Review the changes below before applying them to the public wiki."
    : `${label} will be removed when you save changes.`;
  const changes = action.changes || [];

  return (
    <div className="admin-modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        className={`admin-modal editor-confirm-modal ${isSave ? "" : "compact"}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="editor-confirm-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-modal-header editor-save-confirm-header">
          <div className="admin-notice-heading">
            <span className={`admin-notice-icon ${isSave ? "editor-save-icon" : "danger"}`}>
              {isSave ? <Save aria-hidden="true" size={18} /> : <CircleAlert aria-hidden="true" size={18} />}
            </span>
            <div>
              <h2 id="editor-confirm-title">{title}</h2>
              <p>{message}</p>
            </div>
          </div>
          <button className="admin-icon-button modal-close-button" type="button" onClick={onCancel} aria-label="Close">
            <X aria-hidden="true" size={17} />
          </button>
        </div>

        {isSave ? (
          <div className="editor-save-confirm-body">
            <div className="editor-save-summary-box">
              <Save aria-hidden="true" size={16} />
              <span>{changes.length} pending {changes.length === 1 ? "change" : "changes"} will be saved to the public wiki.</span>
            </div>

            <div className="editor-change-scroll">
              <ChangeReviewList changes={changes} onEditChange={onEditChange} />
            </div>
          </div>
        ) : null}

        <div className="admin-modal-actions editor-save-confirm-footer">
          {isSave ? (
            <span>
              <Info aria-hidden="true" size={16} />
              Click "Edit" on any change to modify it before saving.
            </span>
          ) : <span />}
          <button className="admin-secondary-button" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button className={isSave ? "admin-primary-button" : "admin-danger-button"} type="button" onClick={onConfirm}>
            {isSave ? "Save Changes" : "Delete"}
          </button>
        </div>
      </section>
    </div>
  );
}

export function EditorUnsavedChangesModal({ action, isSaving, onCancel, onDiscard, onSave }) {
  if (!action) {
    return null;
  }

  return (
    <div className="admin-modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        className="admin-modal editor-confirm-modal compact editor-unsaved-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="editor-unsaved-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-modal-header editor-save-confirm-header">
          <div className="admin-notice-heading">
            <span className="admin-notice-icon danger">
              <CircleAlert aria-hidden="true" size={18} />
            </span>
            <div>
              <h2 id="editor-unsaved-title">Unsaved Changes</h2>
              <p>{action.recordLabel} has {action.changeCount} unsaved {action.changeCount === 1 ? "change" : "changes"}.</p>
            </div>
          </div>
          <button className="admin-icon-button modal-close-button" type="button" onClick={onCancel} aria-label="Close">
            <X aria-hidden="true" size={17} />
          </button>
        </div>

        <div className="editor-save-confirm-body">
          <div className="editor-change-scroll">
            <ChangeReviewList changes={action.changes || []} showEdit={false} />
          </div>
          <div className="editor-save-summary-box muted">
            <Info aria-hidden="true" size={16} />
            <span>Save or discard these changes before switching to another record.</span>
          </div>
        </div>

        <div className="admin-modal-actions editor-unsaved-actions">
          <button className="admin-secondary-button" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button className="admin-danger-button" type="button" onClick={onDiscard}>
            Discard
          </button>
          <button className="admin-primary-button" type="button" onClick={onSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </section>
    </div>
  );
}
