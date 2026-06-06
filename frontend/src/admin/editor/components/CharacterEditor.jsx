import React from "react";
import {
  BookOpen,
  ChevronUp,
  ExternalLink,
  Info,
  Pencil,
  Plus,
  Quote,
  Save,
  Star,
  Trash2,
} from "lucide-react";

import {
  CHARACTER_SECTIONS,
  formatChapter,
} from "../editorDrafts.js";
import ChapterReferencePicker from "./ChapterReferencePicker.jsx";
import { EditorField, RelationList } from "./EditorPrimitives.jsx";
import {
  AliasEditor,
  CultivationEventEditor,
  ItemRelationshipEditor,
  SkillRelationshipEditor,
} from "./RelationshipEditors.jsx";

function visibleAliases(aliasDrafts) {
  return aliasDrafts
    .filter((alias) => !alias._deleted)
    .sort((a, b) => {
      if (a.is_primary !== b.is_primary) {
        return a.is_primary ? -1 : 1;
      }

      return Number(a.first_seen_chapter?.chapter_number || 0) - Number(b.first_seen_chapter?.chapter_number || 0);
    });
}

function visibleCultivationEvents(cultivationDrafts) {
  return cultivationDrafts
    .filter((event) => !event._deleted)
    .sort((a, b) => Number(b._sort_chapter_number || 0) - Number(a._sort_chapter_number || 0));
}

function visibleRelationships(relationships) {
  return relationships
    .filter((relationship) => !relationship._deleted)
    .sort((a, b) => {
      if (Boolean(a.id) !== Boolean(b.id)) {
        return a.id ? 1 : -1;
      }

      return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
    });
}

export default function CharacterEditor({
  activeSection,
  addAliasDraft,
  addCultivationDraft,
  addItemDraft,
  addSkillDraft,
  aliasDrafts,
  availableItems,
  availableSkills,
  cancelAliasEdit,
  cancelCultivationEdit,
  cancelItemEdit,
  cancelSkillEdit,
  characters,
  cultivationDrafts,
  draft,
  editingAliasKey,
  editingCultivationKey,
  editingItemKey,
  editingSkillKey,
  finishCultivationEdit,
  finishItemEdit,
  finishSkillEdit,
  isLoading,
  isSaving,
  itemDrafts,
  navigateEditorTarget,
  novelId,
  requestAliasDelete,
  requestCultivationDelete,
  requestItemDelete,
  requestSaveCharacter,
  requestSkillDelete,
  resetCharacterDrafts,
  selectedCharacter,
  setActiveSection,
  setChapterValidity,
  setEditingAliasKey,
  setEditingCultivationKey,
  setEditingItemKey,
  setEditingSkillKey,
  setPrimaryAliasDraft,
  showCharacterValidation,
  skillDrafts,
  updateAliasDraft,
  updateCultivationDraft,
  updateDraft,
  updateItemDraft,
  updateSkillDraft,
}) {
  if (isLoading) {
    return <div className="editor-empty-state">Loading characters...</div>;
  }

  if (!characters.length) {
    return <div className="editor-empty-state">No canonical characters yet. Approve records in Review Queue first.</div>;
  }

  if (!selectedCharacter) {
    return <div className="editor-empty-state">Select a character to edit canonical wiki data.</div>;
  }

  const visibleAliasDrafts = visibleAliases(aliasDrafts);
  const visibleCultivationDrafts = visibleCultivationEvents(cultivationDrafts);
  const visibleSkillDrafts = visibleRelationships(skillDrafts);
  const visibleItemDrafts = visibleRelationships(itemDrafts);

  return (
    <section className="editor-main-panel admin-panel">
      <div className="editor-detail-header">
        <div>
          <div className="editor-title-row">
            <h2>{selectedCharacter.name}</h2>
          </div>
        </div>
        <div className="editor-save-actions">
          <button type="button" className="admin-secondary-button" onClick={resetCharacterDrafts}>
            Cancel
          </button>
          <button type="button" className="admin-primary-button" onClick={requestSaveCharacter} disabled={isSaving}>
            <Save aria-hidden="true" size={16} />
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="editor-section-tabs" role="tablist" aria-label="Character editor sections">
        {CHARACTER_SECTIONS.map((section) => (
          <button
            type="button"
            key={section.id}
            className={activeSection === section.id ? "active" : ""}
            onClick={() => setActiveSection(section.id)}
          >
            {section.label}
          </button>
        ))}
      </div>

      {activeSection === "basic" ? (
        <div className="editor-section-body">
          <h3>Basic Information</h3>
          <div className="editor-form-grid">
            <EditorField label="Canonical Name" required>
              <input data-editor-field="name" className={`admin-input ${showCharacterValidation && !draft.name.trim() ? "editor-invalid-control" : ""}`} value={draft.name} onChange={(event) => updateDraft("name", event.target.value)} />
            </EditorField>
            <EditorField label="Status">
              <select data-editor-field="status" className="admin-select" value={draft.status || ""} onChange={(event) => updateDraft("status", event.target.value)}>
                <option value="">Unknown</option>
                <option value="alive">Alive</option>
                <option value="dead">Dead</option>
                <option value="missing">Missing</option>
                <option value="sealed">Sealed</option>
                <option value="reincarnated">Reincarnated</option>
                <option value="historical">Historical</option>
              </select>
            </EditorField>
            <EditorField label="Gender">
              <select data-editor-field="gender" className="admin-select" value={draft.gender || ""} onChange={(event) => updateDraft("gender", event.target.value)}>
                <option value="">Unknown</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="neutral">Neutral</option>
              </select>
            </EditorField>
            <EditorField label="Race / Species">
              <input data-editor-field="race_or_species" className="admin-input" value={draft.race_or_species || ""} onChange={(event) => updateDraft("race_or_species", event.target.value)} />
            </EditorField>
            <EditorField label="Age Text">
              <input data-editor-field="age_text" className="admin-input" value={draft.age_text || ""} onChange={(event) => updateDraft("age_text", event.target.value)} />
            </EditorField>
            <EditorField label="Origin">
              <input data-editor-field="origin" className="admin-input" value={draft.origin || ""} onChange={(event) => updateDraft("origin", event.target.value)} />
            </EditorField>
            <EditorField label="Faction / Affiliation">
              <input data-editor-field="faction_or_affiliation" className="admin-input" value={draft.faction_or_affiliation || ""} onChange={(event) => updateDraft("faction_or_affiliation", event.target.value)} />
            </EditorField>
            <EditorField label="Current Position">
              <input data-editor-field="current_position" className="admin-input" value={draft.current_position || ""} onChange={(event) => updateDraft("current_position", event.target.value)} />
            </EditorField>
          </div>

          <h3>Chapter References</h3>
          <div className="editor-chapter-reference-grid">
            <EditorField label="First Mentioned">
              <div data-editor-field="first_mentioned_chapter_id">
                <ChapterReferencePicker
                  evidenceChapterId={selectedCharacter.evidence?.[0]?.chapter_id}
                  label="First mentioned"
                  novelId={novelId}
                  value={draft.first_mentioned_chapter_id}
                  onChange={(value) => updateDraft("first_mentioned_chapter_id", value)}
                  onValidationChange={(isValid) => setChapterValidity((current) => ({ ...current, first_mentioned_chapter_id: isValid }))}
                />
              </div>
            </EditorField>
            <EditorField label="First Appeared">
              <div data-editor-field="first_appeared_chapter_id">
                <ChapterReferencePicker
                  evidenceChapterId={selectedCharacter.evidence?.[0]?.chapter_id}
                  label="First appeared"
                  novelId={novelId}
                  value={draft.first_appeared_chapter_id}
                  onChange={(value) => updateDraft("first_appeared_chapter_id", value)}
                  onValidationChange={(isValid) => setChapterValidity((current) => ({ ...current, first_appeared_chapter_id: isValid }))}
                />
              </div>
            </EditorField>
          </div>

          <div className="editor-form-grid single">
            <EditorField label="Titles">
              <input data-editor-field="titles" className="admin-input" value={draft.titles || ""} onChange={(event) => updateDraft("titles", event.target.value)} />
            </EditorField>
            <EditorField label="Description">
              <textarea data-editor-field="description" className="admin-textarea" rows={5} value={draft.description || ""} onChange={(event) => updateDraft("description", event.target.value)} />
            </EditorField>
          </div>
        </div>
      ) : null}

      {activeSection === "aliases" ? (
        <div className="editor-section-body">
          <div className="editor-alias-toolbar">
            <div>
              <h3>Aliases ({visibleAliasDrafts.length})</h3>
              <p>Manage alternate names and titles used for this character.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addAliasDraft}>
              <Plus aria-hidden="true" size={16} />
              Add Alias
            </button>
          </div>
          <div className="editor-alias-list">
            {visibleAliasDrafts.length ? visibleAliasDrafts.map((aliasDraft) => (
              editingAliasKey === aliasDraft.client_key ? (
                <AliasEditor
                  aliases={aliasDrafts}
                  key={aliasDraft.client_key}
                  draft={aliasDraft}
                  mode={aliasDraft.id ? "edit" : "create"}
                  novelId={novelId}
                  onCancel={() => cancelAliasEdit(aliasDraft)}
                  onChange={(nextDraft) => updateAliasDraft(aliasDraft.client_key, nextDraft)}
                  onDone={() => setEditingAliasKey(null)}
                />
              ) : (
                <article className="editor-alias-compact-row" data-editor-row={aliasDraft.client_key} key={aliasDraft.client_key}>
                  <div className="editor-alias-name">
                    <strong>{aliasDraft.alias || "Untitled alias"}</strong>
                    {aliasDraft.is_primary ? (
                      <span className="editor-alias-primary-badge">
                        <Star aria-hidden="true" size={13} />
                        Primary
                      </span>
                    ) : (
                      <button type="button" className="editor-alias-primary-action" onClick={() => setPrimaryAliasDraft(aliasDraft.client_key)} aria-label={`Set ${aliasDraft.alias || "alias"} as primary`}>
                        <Star aria-hidden="true" size={13} />
                        Primary
                      </button>
                    )}
                  </div>
                  <div className="editor-alias-chapter">
                    <span>
                      <BookOpen aria-hidden="true" size={15} />
                      First Mentioned
                    </span>
                    <strong>{aliasDraft.first_seen_chapter ? formatChapter(aliasDraft.first_seen_chapter) : "Not linked"}</strong>
                  </div>
                  <figure className="editor-alias-evidence-card">
                    <Quote aria-hidden="true" size={18} />
                    <blockquote>{aliasDraft.evidence || "No evidence recorded for this alias."}</blockquote>
                    {aliasDraft.first_seen_chapter ? <figcaption>- Chapter {aliasDraft.first_seen_chapter.chapter_number}</figcaption> : null}
                  </figure>
                  <div className="editor-alias-actions">
                    <button type="button" className="admin-icon-button" onClick={() => setEditingAliasKey(aliasDraft.client_key)} aria-label="Edit alias">
                      <Pencil aria-hidden="true" size={15} />
                    </button>
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestAliasDelete(aliasDraft)} aria-label="Delete alias">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </article>
              )
            )) : <div className="editor-empty-inline">No aliases attached yet.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "cultivation" ? (
        <div className="editor-section-body">
          <div className="editor-cultivation-toolbar">
            <div>
              <h3>Cultivation History ({visibleCultivationDrafts.length})</h3>
              <p>All known cultivation / realm breakthroughs history.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addCultivationDraft}>
              <Plus aria-hidden="true" size={16} />
              Add Breakthrough
            </button>
          </div>
          <div className="editor-cultivation-list">
            {visibleCultivationDrafts.length ? visibleCultivationDrafts.map((eventDraft, index) => (
              <article
                className={`editor-cultivation-row ${index === 0 ? "current" : ""} ${editingCultivationKey === eventDraft.client_key ? "editing" : ""}`}
                data-editor-row={eventDraft.client_key}
                key={eventDraft.client_key}
              >
                <div className="editor-cultivation-row-header">
                  <div className="editor-cultivation-summary">
                    {index === 0 ? <em>CURRENT</em> : null}
                    <strong>{eventDraft.cultivation_level || "Untitled breakthrough"}</strong>
                    <span className="editor-cultivation-chapter-line">
                      <BookOpen aria-hidden="true" size={15} />
                      {eventDraft.chapter ? formatChapter(eventDraft.chapter) : "No chapter linked"}
                    </span>
                  </div>
                  <div className="editor-cultivation-actions">
                    {editingCultivationKey === eventDraft.client_key ? (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingCultivationKey(null)} aria-label="Collapse cultivation editor">
                        <ChevronUp aria-hidden="true" size={15} />
                      </button>
                    ) : (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingCultivationKey(eventDraft.client_key)} aria-label="Edit cultivation breakthrough">
                        <Pencil aria-hidden="true" size={15} />
                      </button>
                    )}
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestCultivationDelete(eventDraft)} aria-label="Delete cultivation breakthrough">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
                {editingCultivationKey === eventDraft.client_key ? (
                  <CultivationEventEditor
                    draft={eventDraft}
                    mode={eventDraft.id ? "edit" : "create"}
                    novelId={novelId}
                    onCancel={() => cancelCultivationEdit(eventDraft)}
                    onChange={(nextDraft) => updateCultivationDraft(eventDraft.client_key, nextDraft)}
                    onDone={() => finishCultivationEdit(eventDraft)}
                  />
                ) : null}
              </article>
            )) : <div className="editor-empty-inline">No cultivation breakthroughs recorded yet.</div>}
          </div>
          <div className="editor-tip-bar">
            <Info aria-hidden="true" size={16} />
            <span>Entries are ordered by chapter, newest first. The latest entry is treated as the current cultivation realm.</span>
          </div>
        </div>
      ) : null}

      {activeSection === "skills" ? (
        <div className="editor-section-body">
          <div className="editor-cultivation-toolbar">
            <div>
              <h3>Skills ({visibleSkillDrafts.length})</h3>
              <p>Skills attached to this character.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addSkillDraft}>
              <Plus aria-hidden="true" size={16} />
              Attach Skill
            </button>
          </div>
          <div className="editor-cultivation-list">
            {visibleSkillDrafts.length ? visibleSkillDrafts.map((skillDraft) => (
              <article
                className={`editor-cultivation-row ${editingSkillKey === skillDraft.client_key ? "editing" : ""}`}
                data-editor-row={skillDraft.client_key}
                key={skillDraft.client_key}
              >
                <div className="editor-cultivation-row-header">
                  <div className="editor-cultivation-summary">
                    <strong>{skillDraft.skill_name || "Select a skill"}</strong>
                    <span className="editor-cultivation-chapter-line">
                      <BookOpen aria-hidden="true" size={15} />
                      {skillDraft.chapter ? formatChapter(skillDraft.chapter) : "No chapter linked"}
                    </span>
                  </div>
                  <div className="editor-cultivation-actions">
                    {skillDraft.skill_id ? (
                      <button
                        type="button"
                        className="admin-icon-button"
                        onClick={() => navigateEditorTarget({
                          entity: "skills",
                          section: "basic",
                          skillId: skillDraft.skill_id,
                        })}
                        aria-label={`Open ${skillDraft.skill_name || "skill"} in skill editor`}
                      >
                        <ExternalLink aria-hidden="true" size={15} />
                      </button>
                    ) : null}
                    {editingSkillKey === skillDraft.client_key ? (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingSkillKey(null)} aria-label="Collapse skill editor">
                        <ChevronUp aria-hidden="true" size={15} />
                      </button>
                    ) : (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingSkillKey(skillDraft.client_key)} aria-label="Edit attached skill">
                        <Pencil aria-hidden="true" size={15} />
                      </button>
                    )}
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestSkillDelete(skillDraft)} aria-label="Remove attached skill">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
                {editingSkillKey === skillDraft.client_key ? (
                  <SkillRelationshipEditor
                    availableSkills={availableSkills}
                    draft={skillDraft}
                    novelId={novelId}
                    relationships={skillDrafts}
                    onCancel={() => cancelSkillEdit(skillDraft)}
                    onChange={(nextDraft) => updateSkillDraft(skillDraft.client_key, nextDraft)}
                    onDone={() => finishSkillEdit(skillDraft)}
                  />
                ) : null}
              </article>
            )) : <div className="editor-empty-inline">No skills attached to this character yet.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "items" ? (
        <div className="editor-section-body">
          <div className="editor-cultivation-toolbar">
            <div>
              <h3>Items ({visibleItemDrafts.length})</h3>
              <p>Items attached to this character.</p>
            </div>
            <button type="button" className="admin-primary-button" onClick={addItemDraft}>
              <Plus aria-hidden="true" size={16} />
              Attach Item
            </button>
          </div>
          <div className="editor-cultivation-list">
            {visibleItemDrafts.length ? visibleItemDrafts.map((itemDraft) => (
              <article
                className={`editor-cultivation-row ${editingItemKey === itemDraft.client_key ? "editing" : ""}`}
                data-editor-row={itemDraft.client_key}
                key={itemDraft.client_key}
              >
                <div className="editor-cultivation-row-header">
                  <div className="editor-cultivation-summary">
                    <strong>{itemDraft.item_name || "Select an item"}</strong>
                    <span className="editor-cultivation-chapter-line">
                      <BookOpen aria-hidden="true" size={15} />
                      {itemDraft.chapter ? formatChapter(itemDraft.chapter) : "No chapter linked"}
                    </span>
                  </div>
                  <div className="editor-cultivation-actions">
                    {itemDraft.item_id ? (
                      <button
                        type="button"
                        className="admin-icon-button"
                        onClick={() => navigateEditorTarget({
                          entity: "items",
                          section: "basic",
                          itemId: itemDraft.item_id,
                        })}
                        aria-label={`Open ${itemDraft.item_name || "item"} in item editor`}
                      >
                        <ExternalLink aria-hidden="true" size={15} />
                      </button>
                    ) : null}
                    {editingItemKey === itemDraft.client_key ? (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingItemKey(null)} aria-label="Collapse item editor">
                        <ChevronUp aria-hidden="true" size={15} />
                      </button>
                    ) : (
                      <button type="button" className="admin-icon-button" onClick={() => setEditingItemKey(itemDraft.client_key)} aria-label="Edit attached item">
                        <Pencil aria-hidden="true" size={15} />
                      </button>
                    )}
                    <button type="button" className="admin-danger-button ghost" onClick={() => requestItemDelete(itemDraft)} aria-label="Remove attached item">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
                {editingItemKey === itemDraft.client_key ? (
                  <ItemRelationshipEditor
                    availableItems={availableItems}
                    draft={itemDraft}
                    novelId={novelId}
                    relationships={itemDrafts}
                    onCancel={() => cancelItemEdit(itemDraft)}
                    onChange={(nextDraft) => updateItemDraft(itemDraft.client_key, nextDraft)}
                    onDone={() => finishItemEdit(itemDraft)}
                  />
                ) : null}
              </article>
            )) : <div className="editor-empty-inline">No items attached to this character yet.</div>}
          </div>
        </div>
      ) : null}

      {activeSection === "evidence" ? (
        <div className="editor-section-body">
          <h3>Evidence</h3>
          {selectedCharacter.evidence?.length ? (
            <div className="editor-evidence-list">
              {selectedCharacter.evidence.map((evidence) => (
                <article className="editor-evidence-row" key={evidence.id}>
                  <blockquote>{evidence.evidence_text}</blockquote>
                  <small>{formatChapter(evidence.chapter)}</small>
                </article>
              ))}
            </div>
          ) : <div className="editor-empty-inline">No direct evidence snippets attached to this character yet.</div>}
        </div>
      ) : null}

      {activeSection === "notes" ? (
        <div className="editor-section-body">
          <h3>Admin Notes</h3>
          <textarea data-editor-field="admin_notes" className="admin-textarea" rows={6} value={draft.admin_notes || ""} onChange={(event) => updateDraft("admin_notes", event.target.value)} />
          <h3>Metadata History</h3>
          <RelationList
            rows={selectedCharacter.metadata_history}
            emptyMessage="No metadata history for this character."
            renderTitle={(row) => `${row.field_name}: ${row.proposed_value}`}
            renderMeta={(row) => row.extraction_reason || row.evidence_text || "Metadata change"}
          />
        </div>
      ) : null}
    </section>
  );
}
