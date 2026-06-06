import React from "react";
import {
  BookOpen,
  ChevronUp,
  ExternalLink,
  Pencil,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import {
  formatChapter,
  ITEM_CATEGORIES,
  ITEM_SECTIONS,
} from "../editorDrafts.js";
import { EditorField } from "./EditorPrimitives.jsx";
import { ItemCharacterRelationshipEditor } from "./RelationshipEditors.jsx";

function visibleCharacterRelationships(relationships) {
  return relationships
    .filter((relationship) => !relationship._deleted)
    .sort((a, b) => {
      if (Boolean(a.id) !== Boolean(b.id)) {
        return a.id ? 1 : -1;
      }

      return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
    });
}

export default function ItemEditor({
  activeSection,
  addItemCharacterDraft,
  availableItems,
  canonicalItemDraft,
  cancelItemCharacterEdit,
  characters,
  editingItemCharacterKey,
  finishItemCharacterEdit,
  isLoading,
  isSaving,
  itemCharacterDrafts,
  navigateEditorTarget,
  novelId,
  requestItemCharacterDelete,
  requestSaveCanonicalItem,
  resetCanonicalItemDrafts,
  selectedCanonicalItem,
  setActiveSection,
  setCanonicalItemDraft,
  setEditingItemCharacterKey,
  setShowCanonicalItemValidation,
  showCanonicalItemValidation,
  updateItemCharacterDraft,
}) {
  if (isLoading) {
    return <div className="editor-empty-state">Loading items...</div>;
  }

  if (!availableItems.length) {
    return <div className="editor-empty-state">No canonical items yet. Approve records in Review Queue first.</div>;
  }

  if (!selectedCanonicalItem) {
    return <div className="editor-empty-state">Select an item to edit canonical wiki data.</div>;
  }

  const visibleItemCharacterDrafts = visibleCharacterRelationships(itemCharacterDrafts);

  return (
    <section className="editor-main-panel admin-panel">
      <div className="editor-detail-header">
        <div>
          <div className="editor-title-row"><h2>{selectedCanonicalItem.name}</h2></div>
        </div>
        <div className="editor-save-actions">
          <button type="button" className="admin-secondary-button" onClick={resetCanonicalItemDrafts}>Cancel</button>
          <button
            type="button"
            className="admin-primary-button"
            disabled={isSaving}
            onClick={requestSaveCanonicalItem}
          >
            <Save aria-hidden="true" size={16} />
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="editor-section-tabs" role="tablist" aria-label="Item editor sections">
        {ITEM_SECTIONS.map((section) => (
          <button type="button" key={section.id} className={activeSection === section.id ? "active" : ""} onClick={() => setActiveSection(section.id)}>
            {section.label}
          </button>
        ))}
      </div>

      {activeSection === "basic" ? (
        <div className="editor-section-body">
          <h3>Basic Information</h3>
          <div className="editor-form-grid">
            <EditorField label="Canonical Name" required>
              <input
                data-editor-field="name"
                className={`admin-input ${showCanonicalItemValidation && !canonicalItemDraft.name.trim() ? "editor-invalid-control" : ""}`}
                value={canonicalItemDraft.name}
                onChange={(event) => {
                  setShowCanonicalItemValidation(false);
                  setCanonicalItemDraft((current) => ({ ...current, name: event.target.value }));
                }}
              />
            </EditorField>
            <EditorField label="Category">
              <select
                data-editor-field="category"
                className="admin-select"
                value={canonicalItemDraft.category}
                onChange={(event) => setCanonicalItemDraft((current) => ({ ...current, category: event.target.value }))}
              >
                <option value="">No category</option>
                {ITEM_CATEGORIES.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
            </EditorField>
          </div>
          <div className="editor-form-grid single">
            <EditorField label="Description">
              <textarea data-editor-field="description" className="admin-textarea" rows={6} value={canonicalItemDraft.description} onChange={(event) => setCanonicalItemDraft((current) => ({ ...current, description: event.target.value }))} />
            </EditorField>
          </div>
        </div>
      ) : null}

      {activeSection === "characters" ? (
        <div className="editor-section-body">
          <div className="editor-cultivation-toolbar">
            <div>
              <h3>Characters ({visibleItemCharacterDrafts.length})</h3>
              <p>Characters currently attached to this item.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addItemCharacterDraft}>
              <Plus aria-hidden="true" size={16} />
              Attach Character
            </button>
          </div>
          <div className="editor-cultivation-list">
            {visibleItemCharacterDrafts.length ? visibleItemCharacterDrafts.map((row) => (
              <article
                className={`editor-cultivation-row ${editingItemCharacterKey === row.client_key ? "editing" : ""}`}
                data-editor-row={row.client_key}
                key={row.client_key}
              >
                <div className="editor-cultivation-row-header">
                  <div className="editor-cultivation-summary">
                    <strong>{row.character_name || "Character"}</strong>
                    <span className="editor-cultivation-chapter-line">
                      <BookOpen aria-hidden="true" size={15} />
                      {row.chapter ? formatChapter(row.chapter) : "No chapter linked"}
                    </span>
                    {row.description ? <span className="editor-relationship-note">{row.description}</span> : null}
                  </div>
                  <div className="editor-cultivation-actions">
                    {row.character_id ? (
                      <button
                        type="button"
                        className="admin-icon-button"
                        onClick={() => navigateEditorTarget({
                          characterId: row.character_id,
                          entity: "characters",
                          section: "items",
                        })}
                        aria-label={`Open ${row.character_name || "character"} in character editor`}
                      >
                        <ExternalLink aria-hidden="true" size={15} />
                      </button>
                    ) : null}
                    {editingItemCharacterKey === row.client_key ? (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingItemCharacterKey(null)} aria-label="Collapse character item editor">
                        <ChevronUp aria-hidden="true" size={15} />
                      </button>
                    ) : (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingItemCharacterKey(row.client_key)} aria-label="Edit attached character">
                        <Pencil aria-hidden="true" size={15} />
                      </button>
                    )}
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestItemCharacterDelete(row)} aria-label="Remove attached character">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
                {editingItemCharacterKey === row.client_key ? (
                  <ItemCharacterRelationshipEditor
                    availableCharacters={characters}
                    draft={row}
                    novelId={novelId}
                    relationships={itemCharacterDrafts}
                    onCancel={() => cancelItemCharacterEdit(row)}
                    onChange={(nextDraft) => updateItemCharacterDraft(row.client_key, nextDraft)}
                    onDone={() => finishItemCharacterEdit(row)}
                  />
                ) : null}
              </article>
            )) : <div className="editor-empty-inline">No characters are attached to this item.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "evidence" ? (
        <div className="editor-section-body">
          <h3>Item Evidence</h3>
          {selectedCanonicalItem.evidence?.length ? (
            <div className="editor-evidence-list">
              {selectedCanonicalItem.evidence.map((evidence) => (
                <article className="editor-evidence-row" key={evidence.id}>
                  <blockquote>{evidence.evidence_text}</blockquote>
                  <small>{formatChapter(evidence.chapter)}</small>
                </article>
              ))}
            </div>
          ) : <div className="editor-empty-inline">No direct evidence attached to this item.</div>}
        </div>
      ) : null}

      {activeSection === "notes" ? (
        <div className="editor-section-body">
          <h3>Admin Notes</h3>
          <textarea data-editor-field="admin_notes" className="admin-textarea" rows={7} value={canonicalItemDraft.admin_notes} onChange={(event) => setCanonicalItemDraft((current) => ({ ...current, admin_notes: event.target.value }))} />
        </div>
      ) : null}
    </section>
  );
}
