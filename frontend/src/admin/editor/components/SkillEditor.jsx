import React from "react";
import {
  BookOpen,
  ChevronUp,
  ExternalLink,
  Pencil,
  Plus,
  Quote,
  Save,
  Trash2,
} from "lucide-react";

import {
  formatChapter,
  SKILL_CATEGORIES,
  SKILL_SECTIONS,
} from "../editorDrafts.js";
import { EditorField } from "./EditorPrimitives.jsx";
import {
  AliasEditor,
  SkillCharacterRelationshipEditor,
} from "./RelationshipEditors.jsx";

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

export default function SkillEditor({
  activeSection,
  addCanonicalSkillAliasDraft,
  addSkillCharacterDraft,
  availableSkills,
  cancelCanonicalSkillAliasEdit,
  cancelSkillCharacterEdit,
  canonicalSkillDraft,
  characters,
  editingSkillAliasKey,
  editingSkillCharacterKey,
  finishSkillCharacterEdit,
  isLoading,
  isSaving,
  navigateEditorTarget,
  novelId,
  requestSaveCanonicalSkill,
  requestSkillCharacterDelete,
  resetCanonicalSkillDrafts,
  selectedCanonicalSkill,
  setActiveSection,
  setCanonicalSkillDraft,
  setConfirmDelete,
  setEditingSkillAliasKey,
  setEditingSkillCharacterKey,
  setShowCanonicalSkillValidation,
  showCanonicalSkillValidation,
  skillAliasDrafts,
  skillCharacterDrafts,
  updateCanonicalSkillAliasDraft,
  updateSkillCharacterDraft,
}) {
  if (isLoading) {
    return <div className="editor-empty-state">Loading skills...</div>;
  }

  if (!availableSkills.length) {
    return <div className="editor-empty-state">No canonical skills yet. Approve records in Review Queue first.</div>;
  }

  if (!selectedCanonicalSkill) {
    return <div className="editor-empty-state">Select a skill to edit canonical wiki data.</div>;
  }

  const visibleAliases = skillAliasDrafts.filter((alias) => !alias._deleted);
  const visibleSkillCharacterDrafts = visibleCharacterRelationships(skillCharacterDrafts);

  return (
    <section className="editor-main-panel admin-panel">
      <div className="editor-detail-header">
        <div>
          <div className="editor-title-row"><h2>{selectedCanonicalSkill.name}</h2></div>
        </div>
        <div className="editor-save-actions">
          <button type="button" className="admin-secondary-button" onClick={resetCanonicalSkillDrafts}>Cancel</button>
          <button
            type="button"
            className="admin-primary-button"
            disabled={isSaving}
            onClick={requestSaveCanonicalSkill}
          >
            <Save aria-hidden="true" size={16} />
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="editor-section-tabs" role="tablist" aria-label="Skill editor sections">
        {SKILL_SECTIONS.map((section) => (
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
                className={`admin-input ${showCanonicalSkillValidation && !canonicalSkillDraft.name.trim() ? "editor-invalid-control" : ""}`}
                value={canonicalSkillDraft.name}
                onChange={(event) => {
                  setShowCanonicalSkillValidation(false);
                  setCanonicalSkillDraft((current) => ({ ...current, name: event.target.value }));
                }}
              />
            </EditorField>
            <EditorField label="Category">
              <select
                data-editor-field="category"
                className="admin-select"
                value={canonicalSkillDraft.category}
                onChange={(event) => setCanonicalSkillDraft((current) => ({ ...current, category: event.target.value }))}
              >
                <option value="">No category</option>
                {SKILL_CATEGORIES.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
            </EditorField>
          </div>
          <div className="editor-form-grid single">
            <EditorField label="Description">
              <textarea data-editor-field="description" className="admin-textarea" rows={6} value={canonicalSkillDraft.description} onChange={(event) => setCanonicalSkillDraft((current) => ({ ...current, description: event.target.value }))} />
            </EditorField>
          </div>
        </div>
      ) : null}

      {activeSection === "aliases" ? (
        <div className="editor-section-body">
          <div className="editor-alias-toolbar">
            <div><h3>Aliases ({visibleAliases.length})</h3><p>Manage alternate names used for this skill.</p></div>
            <button type="button" className="admin-primary-button" onClick={addCanonicalSkillAliasDraft}><Plus aria-hidden="true" size={16} />Add Alias</button>
          </div>
          <div className="editor-alias-list">
            {visibleAliases.length ? visibleAliases.map((aliasDraft) => (
              editingSkillAliasKey === aliasDraft.client_key ? (
                <AliasEditor
                  aliases={skillAliasDrafts}
                  key={aliasDraft.client_key}
                  draft={aliasDraft}
                  mode={aliasDraft.id ? "edit" : "create"}
                  novelId={novelId}
                  onCancel={() => cancelCanonicalSkillAliasEdit(aliasDraft)}
                  onChange={(nextDraft) => updateCanonicalSkillAliasDraft(aliasDraft.client_key, nextDraft)}
                  onDone={() => setEditingSkillAliasKey(null)}
                />
              ) : (
                <article className="editor-alias-compact-row" data-editor-row={aliasDraft.client_key} key={aliasDraft.client_key}>
                  <div className="editor-alias-name"><strong>{aliasDraft.alias}</strong></div>
                  <div className="editor-alias-chapter">
                    <span><BookOpen aria-hidden="true" size={15} />First Mentioned</span>
                    <strong>{aliasDraft.first_seen_chapter ? formatChapter(aliasDraft.first_seen_chapter) : "Not linked"}</strong>
                  </div>
                  <figure className="editor-alias-evidence-card">
                    <Quote aria-hidden="true" size={18} />
                    <blockquote>{aliasDraft.evidence || "No evidence recorded for this alias."}</blockquote>
                  </figure>
                  <div className="editor-alias-actions">
                    <button type="button" className="admin-icon-button" onClick={() => setEditingSkillAliasKey(aliasDraft.client_key)} aria-label="Edit skill alias"><Pencil aria-hidden="true" size={15} /></button>
                    <button type="button" className="admin-danger-button ghost" onClick={() => setConfirmDelete({ type: "skill_alias", draft: aliasDraft })} aria-label="Delete skill alias"><Trash2 aria-hidden="true" size={15} /></button>
                  </div>
                </article>
              )
            )) : <div className="editor-empty-inline">No aliases recorded for this skill.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "characters" ? (
        <div className="editor-section-body">
          <div className="editor-cultivation-toolbar">
            <div>
              <h3>Characters ({visibleSkillCharacterDrafts.length})</h3>
              <p>Characters currently attached to this skill.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addSkillCharacterDraft}>
              <Plus aria-hidden="true" size={16} />
              Attach Character
            </button>
          </div>
          <div className="editor-cultivation-list">
            {visibleSkillCharacterDrafts.length ? visibleSkillCharacterDrafts.map((row) => (
              <article
                className={`editor-cultivation-row ${editingSkillCharacterKey === row.client_key ? "editing" : ""}`}
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
                          section: "skills",
                        })}
                        aria-label={`Open ${row.character_name || "character"} in character editor`}
                      >
                        <ExternalLink aria-hidden="true" size={15} />
                      </button>
                    ) : null}
                    {editingSkillCharacterKey === row.client_key ? (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingSkillCharacterKey(null)} aria-label="Collapse character skill editor">
                        <ChevronUp aria-hidden="true" size={15} />
                      </button>
                    ) : (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingSkillCharacterKey(row.client_key)} aria-label="Edit attached character">
                        <Pencil aria-hidden="true" size={15} />
                      </button>
                    )}
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestSkillCharacterDelete(row)} aria-label="Remove attached character">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
                {editingSkillCharacterKey === row.client_key ? (
                  <SkillCharacterRelationshipEditor
                    availableCharacters={characters}
                    draft={row}
                    novelId={novelId}
                    relationships={skillCharacterDrafts}
                    onCancel={() => cancelSkillCharacterEdit(row)}
                    onChange={(nextDraft) => updateSkillCharacterDraft(row.client_key, nextDraft)}
                    onDone={() => finishSkillCharacterEdit(row)}
                  />
                ) : null}
              </article>
            )) : <div className="editor-empty-inline">No characters are attached to this skill.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "evidence" ? (
        <div className="editor-section-body">
          <h3>Skill Evidence</h3>
          {selectedCanonicalSkill.evidence?.length ? (
            <div className="editor-evidence-list">
              {selectedCanonicalSkill.evidence.map((evidence) => (
                <article className="editor-evidence-row" key={evidence.id}>
                  <blockquote>{evidence.evidence_text}</blockquote>
                  <small>{formatChapter(evidence.chapter)}</small>
                </article>
              ))}
            </div>
          ) : <div className="editor-empty-inline">No direct evidence attached to this skill.</div>}
        </div>
      ) : null}

      {activeSection === "notes" ? (
        <div className="editor-section-body">
          <h3>Admin Notes</h3>
          <textarea data-editor-field="admin_notes" className="admin-textarea" rows={7} value={canonicalSkillDraft.admin_notes} onChange={(event) => setCanonicalSkillDraft((current) => ({ ...current, admin_notes: event.target.value }))} />
        </div>
      ) : null}
    </section>
  );
}
