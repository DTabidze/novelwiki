import React from "react";

import ChapterReferencePicker from "./ChapterReferencePicker.jsx";
import { EditorField } from "./EditorPrimitives.jsx";
import {
  CharacterReferencePicker,
  ItemReferencePicker,
  SkillReferencePicker,
} from "./ReferencePickers.jsx";

export function AliasEditor({ aliases, draft, mode, novelId, onCancel, onChange, onDone }) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingAlias = showValidation && !draft.alias.trim();
  const isMissingChapter = showValidation && !draft.first_seen_chapter_id;
  const hasDuplicate = aliases.some((alias) => (
    alias.client_key !== draft.client_key
    && !alias._deleted
    && alias.alias.trim().toLowerCase() === draft.alias.trim().toLowerCase()
  ));
  const isDuplicate = showValidation && hasDuplicate;

  function handleDone() {
    if (!draft.alias.trim() || !draft.first_seen_chapter_id || hasDuplicate) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-alias-editor">
      <div className="editor-alias-editor-header">
        <strong>{mode === "create" ? "Add Alias" : "Edit Alias"}</strong>
      </div>
      <div className="editor-alias-editor-grid">
        <EditorField label="Alias Name" required>
          <input
            className={`admin-input ${isMissingAlias || isDuplicate ? "editor-invalid-control" : ""}`}
            placeholder="Alias name"
            value={draft.alias}
            onChange={(event) => onChange({ ...draft, alias: event.target.value })}
          />
          {isDuplicate ? <small className="editor-field-error">This alias is already used by the character.</small> : null}
        </EditorField>
        <EditorField label="First Mentioned Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Alias first mentioned"
            novelId={novelId}
            value={draft.first_seen_chapter_id}
            onChange={(value, chapter) => onChange({ ...draft, first_seen_chapter_id: value, first_seen_chapter: chapter })}
          />
        </EditorField>
      </div>
      <EditorField label="Evidence">
        <textarea
          className="admin-textarea"
          rows={3}
          placeholder="Exact quote or passage for this alias"
          value={draft.evidence}
          onChange={(event) => onChange({ ...draft, evidence: event.target.value })}
        />
      </EditorField>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>
          Done
        </button>
      </div>
    </div>
  );
}

export function CultivationEventEditor({ draft, novelId, onCancel, onChange, onDone }) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingLevel = showValidation && !draft.cultivation_level.trim();
  const isMissingChapter = showValidation && !draft.chapter_id;

  function handleDone() {
    if (!draft.cultivation_level.trim()) {
      setShowValidation(true);
      return;
    }

    if (!draft.chapter_id) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-cultivation-editor">
      <div className="editor-cultivation-editor-grid">
        <EditorField label="Cultivation Level" required>
          <input
            className={`admin-input ${isMissingLevel ? "editor-invalid-control" : ""}`}
            placeholder="Foundation Establishment"
            value={draft.cultivation_level}
            onChange={(event) => {
              onChange({ ...draft, cultivation_level: event.target.value });
            }}
          />
        </EditorField>
        <EditorField label="Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Cultivation chapter"
            novelId={novelId}
            placeholder="Chapter number"
            value={draft.chapter_id}
            onChange={(value, chapter) => {
              onChange({ ...draft, chapter_id: value, chapter });
            }}
          />
        </EditorField>
        <EditorField label="Evidence">
          <textarea
            className="admin-textarea"
            rows={3}
            placeholder="Exact quote or passage that proves this breakthrough"
            value={draft.evidence}
            onChange={(event) => onChange({ ...draft, evidence: event.target.value })}
          />
        </EditorField>
      </div>
      <EditorField label="Notes (Optional)">
        <input
          className="admin-input"
          placeholder="Optional notes about this breakthrough"
          value={draft.notes}
          onChange={(event) => onChange({ ...draft, notes: event.target.value })}
        />
      </EditorField>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>
          Done
        </button>
      </div>
    </div>
  );
}

export function SkillRelationshipEditor({
  availableSkills,
  draft,
  novelId,
  onCancel,
  onChange,
  onDone,
  relationships,
}) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingSkill = showValidation && !draft.skill_id;
  const isMissingChapter = showValidation && !draft.chapter_id;
  const hasDuplicate = relationships.some((relationship) => (
    relationship.client_key !== draft.client_key
    && !relationship._deleted
    && String(relationship.skill_id) === String(draft.skill_id)
  ));
  const isDuplicate = showValidation && hasDuplicate;

  function isDuplicateSkill(skillId) {
    return relationships.some((relationship) => (
      relationship.client_key !== draft.client_key
      && !relationship._deleted
      && String(relationship.skill_id) === String(skillId)
    ));
  }

  function handleDone() {
    if (!draft.skill_id || !draft.chapter_id || hasDuplicate) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-cultivation-editor">
      <div className="editor-skill-editor-grid">
        <EditorField label="Skill" required>
          <SkillReferencePicker
            availableSkills={availableSkills}
            invalid={isMissingSkill || isDuplicate}
            isDuplicateSkill={isDuplicateSkill}
            value={draft.skill_id}
            onChange={(skillId, skill) => {
              onChange({ ...draft, skill_id: skillId, skill_name: skill?.name || "" });
            }}
          />
          {isDuplicate ? <small className="editor-field-error">This skill is already attached to the character.</small> : null}
        </EditorField>
        <EditorField label="First Known Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Skill first known chapter"
            novelId={novelId}
            value={draft.chapter_id}
            onChange={(value, chapter) => onChange({ ...draft, chapter_id: value, chapter })}
          />
        </EditorField>
        <EditorField label="Evidence (Optional)">
          <textarea
            className="admin-textarea"
            rows={3}
            placeholder="Exact quote or passage proving this character has the skill"
            value={draft.evidence_text}
            onChange={(event) => onChange({ ...draft, evidence_text: event.target.value })}
          />
        </EditorField>
        <EditorField label="Description (Optional)">
          <input
            className="admin-input"
            placeholder="Optional context about this character's skill"
            value={draft.description}
            onChange={(event) => onChange({ ...draft, description: event.target.value })}
          />
        </EditorField>
        <EditorField label="Notes (Optional)">
          <input
            className="admin-input"
            placeholder="Internal notes about this character skill"
            value={draft.admin_notes}
            onChange={(event) => onChange({ ...draft, admin_notes: event.target.value })}
          />
        </EditorField>
      </div>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>Cancel</button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>Done</button>
      </div>
    </div>
  );
}

export function SkillCharacterRelationshipEditor({
  availableCharacters,
  draft,
  novelId,
  onCancel,
  onChange,
  onDone,
  relationships,
}) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingCharacter = showValidation && !draft.character_id;
  const isMissingChapter = showValidation && !draft.chapter_id;
  const hasDuplicate = relationships.some((relationship) => (
    relationship.client_key !== draft.client_key
    && !relationship._deleted
    && String(relationship.character_id) === String(draft.character_id)
  ));
  const isDuplicate = showValidation && hasDuplicate;

  function isDuplicateCharacter(characterId) {
    return relationships.some((relationship) => (
      relationship.client_key !== draft.client_key
      && !relationship._deleted
      && String(relationship.character_id) === String(characterId)
    ));
  }

  function handleDone() {
    if (!draft.character_id || !draft.chapter_id || hasDuplicate) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-cultivation-editor">
      <div className="editor-skill-editor-grid">
        <EditorField label="Character" required>
          <CharacterReferencePicker
            availableCharacters={availableCharacters}
            invalid={isMissingCharacter || isDuplicate}
            isDuplicateCharacter={isDuplicateCharacter}
            value={draft.character_id}
            onChange={(characterId, character) => {
              onChange({ ...draft, character_id: characterId, character_name: character?.name || "" });
            }}
          />
          {isDuplicate ? <small className="editor-field-error">This character is already attached to the skill.</small> : null}
        </EditorField>
        <EditorField label="First Known Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Skill first known chapter"
            novelId={novelId}
            value={draft.chapter_id}
            onChange={(value, chapter) => onChange({ ...draft, chapter_id: value, chapter })}
          />
        </EditorField>
        <EditorField label="Evidence (Optional)">
          <textarea
            className="admin-textarea"
            rows={3}
            placeholder="Exact quote or passage proving this character has the skill"
            value={draft.evidence_text}
            onChange={(event) => onChange({ ...draft, evidence_text: event.target.value })}
          />
        </EditorField>
        <EditorField label="Description (Optional)">
          <input
            className="admin-input"
            placeholder="Optional context about this character's skill"
            value={draft.description}
            onChange={(event) => onChange({ ...draft, description: event.target.value })}
          />
        </EditorField>
        <EditorField label="Notes (Optional)">
          <input
            className="admin-input"
            placeholder="Internal notes about this character skill"
            value={draft.admin_notes}
            onChange={(event) => onChange({ ...draft, admin_notes: event.target.value })}
          />
        </EditorField>
      </div>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>Cancel</button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>Done</button>
      </div>
    </div>
  );
}

export function ItemRelationshipEditor({
  availableItems,
  draft,
  novelId,
  onCancel,
  onChange,
  onDone,
  relationships,
}) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingItem = showValidation && !draft.item_id;
  const isMissingChapter = showValidation && !draft.chapter_id;
  const hasDuplicate = relationships.some((relationship) => (
    relationship.client_key !== draft.client_key
    && !relationship._deleted
    && String(relationship.item_id) === String(draft.item_id)
  ));
  const isDuplicate = showValidation && hasDuplicate;

  function isDuplicateItem(itemId) {
    return relationships.some((relationship) => (
      relationship.client_key !== draft.client_key
      && !relationship._deleted
      && String(relationship.item_id) === String(itemId)
    ));
  }

  function handleDone() {
    if (!draft.item_id || !draft.chapter_id || hasDuplicate) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-cultivation-editor">
      <div className="editor-skill-editor-grid">
        <EditorField label="Item" required>
          <ItemReferencePicker
            availableItems={availableItems}
            invalid={isMissingItem || isDuplicate}
            isDuplicateItem={isDuplicateItem}
            value={draft.item_id}
            onChange={(itemId, item) => {
              onChange({ ...draft, item_id: itemId, item_name: item?.name || "" });
            }}
          />
          {isDuplicate ? <small className="editor-field-error">This item is already attached to the character.</small> : null}
        </EditorField>
        <EditorField label="First Known Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Item first known chapter"
            novelId={novelId}
            value={draft.chapter_id}
            onChange={(value, chapter) => onChange({ ...draft, chapter_id: value, chapter })}
          />
        </EditorField>
        <EditorField label="Evidence (Optional)">
          <textarea
            className="admin-textarea"
            rows={3}
            placeholder="Exact quote or passage proving this character has the item"
            value={draft.evidence_text}
            onChange={(event) => onChange({ ...draft, evidence_text: event.target.value })}
          />
        </EditorField>
        <EditorField label="Description (Optional)">
          <input
            className="admin-input"
            placeholder="Optional context about this character's item"
            value={draft.description}
            onChange={(event) => onChange({ ...draft, description: event.target.value })}
          />
        </EditorField>
        <EditorField label="Notes (Optional)">
          <input
            className="admin-input"
            placeholder="Internal notes about this character item"
            value={draft.admin_notes}
            onChange={(event) => onChange({ ...draft, admin_notes: event.target.value })}
          />
        </EditorField>
      </div>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>Cancel</button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>Done</button>
      </div>
    </div>
  );
}

export function ItemCharacterRelationshipEditor({
  availableCharacters,
  draft,
  novelId,
  onCancel,
  onChange,
  onDone,
  relationships,
}) {
  const [showValidation, setShowValidation] = React.useState(false);
  const isMissingCharacter = showValidation && !draft.character_id;
  const isMissingChapter = showValidation && !draft.chapter_id;
  const hasDuplicate = relationships.some((relationship) => (
    relationship.client_key !== draft.client_key
    && !relationship._deleted
    && String(relationship.character_id) === String(draft.character_id)
  ));
  const isDuplicate = showValidation && hasDuplicate;

  function isDuplicateCharacter(characterId) {
    return relationships.some((relationship) => (
      relationship.client_key !== draft.client_key
      && !relationship._deleted
      && String(relationship.character_id) === String(characterId)
    ));
  }

  function handleDone() {
    if (!draft.character_id || !draft.chapter_id || hasDuplicate) {
      setShowValidation(true);
      return;
    }

    setShowValidation(false);
    onDone();
  }

  return (
    <div className="editor-cultivation-editor">
      <div className="editor-skill-editor-grid">
        <EditorField label="Character" required>
          <CharacterReferencePicker
            availableCharacters={availableCharacters}
            invalid={isMissingCharacter || isDuplicate}
            isDuplicateCharacter={isDuplicateCharacter}
            value={draft.character_id}
            onChange={(characterId, character) => {
              onChange({ ...draft, character_id: characterId, character_name: character?.name || "" });
            }}
          />
          {isDuplicate ? <small className="editor-field-error">This character is already attached to the item.</small> : null}
        </EditorField>
        <EditorField label="First Known Chapter" required>
          <ChapterReferencePicker
            className={isMissingChapter ? "editor-invalid-control" : ""}
            label="Item first known chapter"
            novelId={novelId}
            value={draft.chapter_id}
            onChange={(value, chapter) => onChange({ ...draft, chapter_id: value, chapter })}
          />
        </EditorField>
        <EditorField label="Evidence (Optional)">
          <textarea
            className="admin-textarea"
            rows={3}
            placeholder="Exact quote or passage proving this character has the item"
            value={draft.evidence_text}
            onChange={(event) => onChange({ ...draft, evidence_text: event.target.value })}
          />
        </EditorField>
        <EditorField label="Description (Optional)">
          <input
            className="admin-input"
            placeholder="Optional context about this character's item"
            value={draft.description}
            onChange={(event) => onChange({ ...draft, description: event.target.value })}
          />
        </EditorField>
        <EditorField label="Notes (Optional)">
          <input
            className="admin-input"
            placeholder="Internal notes about this character item"
            value={draft.admin_notes}
            onChange={(event) => onChange({ ...draft, admin_notes: event.target.value })}
          />
        </EditorField>
      </div>
      <div className="editor-row-actions">
        <button type="button" className="editor-inline-cancel-button" onClick={onCancel}>Cancel</button>
        <button type="button" className="editor-inline-done-button" onClick={handleDone}>Done</button>
      </div>
    </div>
  );
}
