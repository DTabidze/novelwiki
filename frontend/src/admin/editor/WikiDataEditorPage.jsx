import React from "react";
import { useSearchParams } from "react-router-dom";
import {
  BookOpen,
  ChevronUp,
  CircleAlert,
  ExternalLink,
  FileText,
  Info,
  Package,
  Pencil,
  Plus,
  Quote,
  Save,
  Search,
  Sparkles,
  Star,
  Timeline,
  Trash2,
  Type,
  Users,
  X,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";
import AdminNoticeModal from "../components/AdminNoticeModal.jsx";
import ChapterReferencePicker from "./components/ChapterReferencePicker.jsx";
import { EditorField, RelationList } from "./components/EditorPrimitives.jsx";
import {
  AliasEditor,
  CultivationEventEditor,
  ItemCharacterRelationshipEditor,
  ItemRelationshipEditor,
  SkillCharacterRelationshipEditor,
  SkillRelationshipEditor,
} from "./components/RelationshipEditors.jsx";
import {
  aliasesToDrafts,
  CHARACTER_FIELDS,
  CHARACTER_SECTIONS,
  characterToDraft,
  cultivationEventsToDrafts,
  emptyDraft,
  formatChapter,
  getCharacterSubtitle,
  ITEM_CATEGORIES,
  ITEM_FIELDS,
  ITEM_SECTIONS,
  itemCharacterRelationshipsToDrafts,
  itemRelationshipsToDrafts,
  itemToDraft,
  normalizePayload,
  SKILL_CATEGORIES,
  skillCharacterRelationshipsToDrafts,
  SKILL_FIELDS,
  SKILL_SECTIONS,
  skillRelationshipsToDrafts,
  skillToDraft,
} from "./editorDrafts.js";

const ENTITY_TABS = [
  { id: "characters", label: "Characters", icon: Users, enabled: true },
  { id: "skills", label: "Skills", icon: Sparkles, enabled: true },
  { id: "items", label: "Items", icon: Package, enabled: true },
  { id: "progression", label: "Cultivation", icon: Timeline, enabled: false },
];

function isKnownEntity(entity) {
  return ENTITY_TABS.some((tab) => tab.id === entity);
}

function isDataBackedEntity(entity) {
  return ["characters", "skills", "items"].includes(entity);
}

function sectionsForEntity(entity) {
  if (entity === "skills") {
    return SKILL_SECTIONS;
  }

  if (entity === "items") {
    return ITEM_SECTIONS;
  }

  if (entity === "characters") {
    return CHARACTER_SECTIONS;
  }

  return [{ id: "basic", label: "Basic Info" }];
}

function initialEntityFromParams(searchParams) {
  const requestedEntity = searchParams.get("entity");
  return isKnownEntity(requestedEntity) ? requestedEntity : "characters";
}

function initialSectionFromParams(searchParams, entity) {
  const requestedSection = searchParams.get("section");
  const sections = sectionsForEntity(entity);
  return sections.some((section) => section.id === requestedSection) ? requestedSection : "basic";
}

const CHARACTER_FIELD_LABELS = {
  name: "Canonical name",
  description: "Description",
  first_mentioned_chapter_id: "First mentioned chapter",
  first_appeared_chapter_id: "First appeared chapter",
  first_seen_chapter_id: "First seen chapter",
  age_text: "Age text",
  gender: "Gender",
  race_or_species: "Race / species",
  race_or_species_source: "Race / species source",
  race_or_species_confidence: "Race / species confidence",
  origin: "Origin",
  faction_or_affiliation: "Faction / affiliation",
  status: "Status",
  titles: "Titles",
  current_cultivation_level: "Current cultivation level",
  current_position: "Current position",
  current_class_rank: "Class rank",
  current_power_rank: "Power rank",
  admin_notes: "Admin notes",
};

const SKILL_FIELD_LABELS = {
  name: "Canonical name",
  category: "Category",
  description: "Description",
  admin_notes: "Admin notes",
};

const ITEM_FIELD_LABELS = {
  name: "Canonical name",
  category: "Category",
  description: "Description",
  admin_notes: "Admin notes",
};

function normalizedChangeValue(value) {
  return String(value ?? "");
}

function displayChangeValue(value, fallback = "Empty") {
  const displayValue = normalizedChangeValue(value).trim();
  return displayValue || fallback;
}

function valuesChanged(left, right) {
  return normalizedChangeValue(left) !== normalizedChangeValue(right);
}

function relationshipDetailValue(relationship, getName) {
  const parts = [
    getName(relationship),
    relationship?.chapter ? formatChapter(relationship.chapter) : null,
    relationship?.description,
    relationship?.evidence_text ? "Evidence attached" : null,
    relationship?.admin_notes ? "Notes attached" : null,
  ].filter(Boolean);

  return parts.join(" · ") || "Untitled record";
}

function fieldSection(field) {
  if (["admin_notes"].includes(field)) {
    return "notes";
  }

  return "basic";
}

function summarizeFieldChanges(fields, draft, original, labels, options = {}) {
  const entityType = options.entityType || "field";
  const entityLabel = options.entityLabel || "record";
  const entityName = options.entityName || original?.name || "this record";

  return fields
    .filter((field) => valuesChanged(draft[field], original?.[field]))
    .map((field) => ({
      id: `${entityType}-field-${field}`,
      operation: "updated",
      entityType: "field",
      label: field === "name"
        ? `Renamed ${entityLabel} ${displayChangeValue(original?.name || entityName, "")}`
        : `Updated ${labels[field] || field.replaceAll("_", " ")} on ${entityLabel} ${entityName}`,
      oldValue: displayChangeValue(original?.[field]),
      newValue: displayChangeValue(draft[field]),
      editTarget: {
        field,
        section: fieldSection(field),
      },
    }));
}

function summarizeAliasChanges(drafts, originalRecord, label = "alias", section = "aliases", options = {}) {
  const originalById = new Map(aliasesToDrafts(originalRecord).map((alias) => [alias.id, alias]));
  const parentLabel = options.parentLabel || "record";
  const parentName = options.parentName || originalRecord?.name || "this record";
  const changes = [];

  drafts.forEach((draft) => {
    if (!draft.id && draft._deleted) {
      return;
    }

    const aliasName = draft.alias || "Untitled alias";

    if (!draft.id) {
      changes.push({
        id: `${section}-added-${draft.client_key}`,
        operation: "added",
        entityType: "alias",
        label: `Added ${label} to ${parentLabel} ${parentName}`,
        displayValue: aliasName,
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
      return;
    }

    const original = originalById.get(draft.id);

    if (draft._deleted) {
      changes.push({
        id: `${section}-removed-${draft.client_key}`,
        operation: "removed",
        entityType: "alias",
        label: `Removed ${label} from ${parentLabel} ${parentName}`,
        displayValue: original?.alias || aliasName,
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
      return;
    }

    if (
      valuesChanged(draft.alias, original?.alias)
      || valuesChanged(draft.first_seen_chapter_id, original?.first_seen_chapter_id)
      || valuesChanged(draft.evidence, original?.evidence)
      || Boolean(draft.is_primary) !== Boolean(original?.is_primary)
    ) {
      changes.push({
        id: `${section}-updated-${draft.client_key}`,
        operation: "updated",
        entityType: "alias",
        label: `Updated ${label} on ${parentLabel} ${parentName}`,
        oldValue: original?.alias || "Untitled alias",
        newValue: aliasName,
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
    }
  });

  return changes;
}

function summarizeRelationshipChanges(drafts, originalDrafts, entityLabel, getName, section, options = {}) {
  const originalById = new Map(originalDrafts.map((relationship) => [relationship.id, relationship]));
  const parentLabel = options.parentLabel || "record";
  const parentName = options.parentName || "this record";
  const changes = [];

  drafts.forEach((draft) => {
    if (!draft.id && draft._deleted) {
      return;
    }

    const name = getName(draft) || `Untitled ${entityLabel}`;

    if (!draft.id) {
      changes.push({
        id: `${section}-added-${draft.client_key}`,
        operation: "added",
        entityType: entityLabel,
        label: `Added ${entityLabel} to ${parentLabel} ${parentName}`,
        displayValue: name,
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
      return;
    }

    const original = originalById.get(draft.id);

    if (draft._deleted) {
      changes.push({
        id: `${section}-removed-${draft.client_key}`,
        operation: "removed",
        entityType: entityLabel,
        label: `Removed ${entityLabel} from ${parentLabel} ${parentName}`,
        displayValue: getName(original || draft) || name,
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
      return;
    }

    if (
      valuesChanged(draft.chapter_id, original?.chapter_id)
      || valuesChanged(draft.description, original?.description)
      || valuesChanged(draft.evidence_text, original?.evidence_text)
      || valuesChanged(draft.admin_notes, original?.admin_notes)
    ) {
      changes.push({
        id: `${section}-updated-${draft.client_key}`,
        operation: "updated",
        entityType: entityLabel,
        label: `Updated ${entityLabel} on ${parentLabel} ${parentName}`,
        oldValue: relationshipDetailValue(original || draft, getName),
        newValue: relationshipDetailValue(draft, getName),
        editTarget: {
          clientKey: draft.client_key,
          section,
        },
      });
    }
  });

  return changes;
}

const CHANGE_GROUPS = [
  { id: "updated", label: "Updated", Icon: Pencil },
  { id: "added", label: "Added", Icon: Plus },
  { id: "removed", label: "Removed", Icon: Trash2 },
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

function EditorConfirmModal({ action, onCancel, onConfirm, onEditChange }) {
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
  const groupedChanges = CHANGE_GROUPS.map((group) => ({
    ...group,
    changes: changes.filter((change) => change.operation === group.id),
  })).filter((group) => group.changes.length);

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

            {groupedChanges.length ? groupedChanges.map(({ id, label: groupLabel, Icon, changes: groupChanges }) => (
              <section className={`editor-change-group ${id}`} key={id}>
                <h3>
                  <span className="editor-change-group-dot" />
                  {groupChanges.length} {groupLabel}
                </h3>
                <div className="editor-change-row-list">
                  {groupChanges.map((change) => (
                    <article className="editor-change-row" key={change.id}>
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
                      <button type="button" className="editor-change-edit-button" onClick={() => onEditChange(change)}>
                        <Pencil aria-hidden="true" size={15} />
                        Edit
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            )) : (
              <div className="editor-save-summary-box muted">
                <Info aria-hidden="true" size={16} />
                <span>Nothing has changed since this record was loaded.</span>
              </div>
            )}
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

function EditorUnsavedChangesModal({ action, isSaving, onCancel, onDiscard, onSave }) {
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

export default function WikiDataEditorPage({ novel }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryString = searchParams.toString();
  const initialEntity = initialEntityFromParams(searchParams);
  const initialSection = initialSectionFromParams(searchParams, initialEntity);
  const skipNextUrlSelectionSyncRef = React.useRef(false);
  const [activeEntity, setActiveEntity] = React.useState(() => initialEntity);
  const [activeSection, setActiveSection] = React.useState(() => initialSection);
  const [sectionByEntity, setSectionByEntity] = React.useState(() => ({
    [initialEntity]: initialSection,
  }));
  const [characters, setCharacters] = React.useState([]);
  const [selectedCharacterId, setSelectedCharacterId] = React.useState(null);
  const [selectedSkillId, setSelectedSkillId] = React.useState(null);
  const [selectedItemId, setSelectedItemId] = React.useState(null);
  const [draft, setDraft] = React.useState(emptyDraft);
  const [canonicalSkillDraft, setCanonicalSkillDraft] = React.useState(() => skillToDraft(null));
  const [skillAliasDrafts, setSkillAliasDrafts] = React.useState([]);
  const [editingSkillAliasKey, setEditingSkillAliasKey] = React.useState(null);
  const [skillCharacterDrafts, setSkillCharacterDrafts] = React.useState([]);
  const [editingSkillCharacterKey, setEditingSkillCharacterKey] = React.useState(null);
  const [canonicalItemDraft, setCanonicalItemDraft] = React.useState(() => itemToDraft(null));
  const [itemCharacterDrafts, setItemCharacterDrafts] = React.useState([]);
  const [editingItemCharacterKey, setEditingItemCharacterKey] = React.useState(null);
  const [aliasDrafts, setAliasDrafts] = React.useState([]);
  const [editingAliasKey, setEditingAliasKey] = React.useState(null);
  const [cultivationDrafts, setCultivationDrafts] = React.useState([]);
  const [editingCultivationKey, setEditingCultivationKey] = React.useState(null);
  const [availableSkills, setAvailableSkills] = React.useState([]);
  const [skillDrafts, setSkillDrafts] = React.useState([]);
  const [editingSkillKey, setEditingSkillKey] = React.useState(null);
  const [availableItems, setAvailableItems] = React.useState([]);
  const [itemDrafts, setItemDrafts] = React.useState([]);
  const [editingItemKey, setEditingItemKey] = React.useState(null);
  const [confirmDelete, setConfirmDelete] = React.useState(null);
  const [isConfirmingSave, setIsConfirmingSave] = React.useState(false);
  const [pendingNavigation, setPendingNavigation] = React.useState(null);
  const [showCharacterValidation, setShowCharacterValidation] = React.useState(false);
  const [showCanonicalSkillValidation, setShowCanonicalSkillValidation] = React.useState(false);
  const [showCanonicalItemValidation, setShowCanonicalItemValidation] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [chapterValidity, setChapterValidity] = React.useState({
    first_mentioned_chapter_id: true,
    first_appeared_chapter_id: true,
  });
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isEntityBrowserOpen, setIsEntityBrowserOpen] = React.useState(false);
  const [error, setError] = React.useState("");

  const selectedCharacter = React.useMemo(
    () => characters.find((character) => character.id === selectedCharacterId) || null,
    [characters, selectedCharacterId]
  );
  const selectedCanonicalSkill = React.useMemo(
    () => availableSkills.find((skill) => skill.id === selectedSkillId) || null,
    [availableSkills, selectedSkillId]
  );
  const selectedCanonicalItem = React.useMemo(
    () => availableItems.find((item) => item.id === selectedItemId) || null,
    [availableItems, selectedItemId]
  );

  React.useEffect(() => {
    setSearch("");
    setIsEntityBrowserOpen(false);
  }, [activeEntity]);

  React.useEffect(() => {
    setSectionByEntity((current) => (
      current[activeEntity] === activeSection
        ? current
        : { ...current, [activeEntity]: activeSection }
    ));
  }, [activeEntity, activeSection]);

  const publicWikiPath = activeEntity === "items" && selectedCanonicalItem
    ? `/wiki/novels/${novel?.id}/items/${selectedCanonicalItem.id}`
    : activeEntity === "skills" && selectedCanonicalSkill
    ? `/wiki/novels/${novel?.id}/skills/${selectedCanonicalSkill.id}`
    : selectedCharacter
      ? `/wiki/novels/${novel?.id}/characters/${selectedCharacter.id}`
      : `/wiki/novels/${novel?.id}`;

  const filteredCharacters = React.useMemo(() => {
    const query = search.trim().toLowerCase();

    return characters.filter((character) => {
      const aliasText = (character.aliases || []).map((alias) => alias.alias).join(" ");
      const matchesSearch = !query || [
        character.name,
        aliasText,
      ].some((value) => String(value || "").toLowerCase().includes(query));

      return matchesSearch;
    });
  }, [characters, search]);
  const filteredCanonicalSkills = React.useMemo(() => {
    const query = search.trim().toLowerCase();

    return availableSkills.filter((skill) => {
      const aliasText = (skill.aliases || []).map((alias) => alias.alias).join(" ");
      return !query || [skill.name, aliasText].some(
        (value) => String(value || "").toLowerCase().includes(query)
      );
    });
  }, [availableSkills, search]);
  const filteredCanonicalItems = React.useMemo(() => {
    const query = search.trim().toLowerCase();

    return availableItems.filter((item) => (
      !query || [item.name].some(
        (value) => String(value || "").toLowerCase().includes(query)
      )
    ));
  }, [availableItems, search]);

  const characterSaveChanges = React.useMemo(() => {
    if (!selectedCharacter) {
      return [];
    }

    return [
      ...summarizeFieldChanges(CHARACTER_FIELDS, draft, selectedCharacter, CHARACTER_FIELD_LABELS, {
        entityLabel: "character",
        entityName: selectedCharacter.name,
        entityType: "character",
      }),
      ...summarizeAliasChanges(aliasDrafts, selectedCharacter, "alias", "aliases", {
        parentLabel: "character",
        parentName: selectedCharacter.name,
      }),
      ...summarizeRelationshipChanges(
        cultivationDrafts,
        cultivationEventsToDrafts(selectedCharacter),
        "cultivation breakthrough",
        (event) => event?.cultivation_level,
        "cultivation",
        {
          parentLabel: "character",
          parentName: selectedCharacter.name,
        }
      ),
      ...summarizeRelationshipChanges(
        skillDrafts,
        skillRelationshipsToDrafts(selectedCharacter),
        "skill",
        (relationship) => relationship?.skill_name,
        "skills",
        {
          parentLabel: "character",
          parentName: selectedCharacter.name,
        }
      ),
      ...summarizeRelationshipChanges(
        itemDrafts,
        itemRelationshipsToDrafts(selectedCharacter),
        "item",
        (relationship) => relationship?.item_name,
        "items",
        {
          parentLabel: "character",
          parentName: selectedCharacter.name,
        }
      ),
    ];
  }, [aliasDrafts, cultivationDrafts, draft, itemDrafts, selectedCharacter, skillDrafts]);

  const skillSaveChanges = React.useMemo(() => {
    if (!selectedCanonicalSkill) {
      return [];
    }

    return [
      ...summarizeFieldChanges(SKILL_FIELDS, canonicalSkillDraft, selectedCanonicalSkill, SKILL_FIELD_LABELS, {
        entityLabel: "skill",
        entityName: selectedCanonicalSkill.name,
        entityType: "skill",
      }),
      ...summarizeAliasChanges(skillAliasDrafts, selectedCanonicalSkill, "skill alias", "aliases", {
        parentLabel: "skill",
        parentName: selectedCanonicalSkill.name,
      }),
      ...summarizeRelationshipChanges(
        skillCharacterDrafts,
        skillCharacterRelationshipsToDrafts(selectedCanonicalSkill),
        "character",
        (relationship) => relationship?.character_name,
        "characters",
        {
          parentLabel: "skill",
          parentName: selectedCanonicalSkill.name,
        }
      ),
    ];
  }, [canonicalSkillDraft, selectedCanonicalSkill, skillAliasDrafts, skillCharacterDrafts]);

  const itemSaveChanges = React.useMemo(() => {
    if (!selectedCanonicalItem) {
      return [];
    }

    return [
      ...summarizeFieldChanges(ITEM_FIELDS, canonicalItemDraft, selectedCanonicalItem, ITEM_FIELD_LABELS, {
        entityLabel: "item",
        entityName: selectedCanonicalItem.name,
        entityType: "item",
      }),
      ...summarizeRelationshipChanges(
        itemCharacterDrafts,
        itemCharacterRelationshipsToDrafts(selectedCanonicalItem),
        "character",
        (relationship) => relationship?.character_name,
        "characters",
        {
          parentLabel: "item",
          parentName: selectedCanonicalItem.name,
        }
      ),
    ];
  }, [canonicalItemDraft, itemCharacterDrafts, selectedCanonicalItem]);

  const activeSaveChanges = activeEntity === "items"
    ? itemSaveChanges
    : activeEntity === "skills"
      ? skillSaveChanges
      : characterSaveChanges;
  const activeRecordLabel = activeEntity === "items"
    ? `Item ${selectedCanonicalItem?.name || "record"}`
    : activeEntity === "skills"
    ? `Skill ${selectedCanonicalSkill?.name || "record"}`
    : `Character ${selectedCharacter?.name || "record"}`;

  function discardCurrentDrafts() {
    if (activeEntity === "items") {
      resetCanonicalItemDrafts();
      return;
    }

    if (activeEntity === "skills") {
      resetCanonicalSkillDrafts();
      return;
    }

    resetCharacterDrafts();
  }

  function shouldGuardNavigation(target) {
    if (!activeSaveChanges.length) {
      return false;
    }

    if (target.entity !== activeEntity) {
      return true;
    }

    if (target.entity === "characters" && target.characterId && Number(target.characterId) !== selectedCharacterId) {
      return true;
    }

    if (target.entity === "skills" && target.skillId && Number(target.skillId) !== selectedSkillId) {
      return true;
    }

    if (target.entity === "items" && target.itemId && Number(target.itemId) !== selectedItemId) {
      return true;
    }

    return false;
  }

  function requestNavigation(target, proceed) {
    if (!shouldGuardNavigation(target)) {
      proceed();
      return;
    }

    setPendingNavigation({
      changeCount: activeSaveChanges.length,
      proceed,
      recordLabel: activeRecordLabel,
    });
  }

  async function loadCharacters() {
    if (!novel?.id) {
      return;
    }

    setIsLoading(true);
    setError("");
    try {
      const [data, skillData, itemData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novel.id}/characters`),
        fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novel.id}/skills`),
        fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novel.id}/items`),
      ]);
      const rows = data.characters || [];
      const requestedCharacterId = Number(searchParams.get("character"));
      setCharacters(rows);
      setAvailableSkills(skillData.skills || []);
      setAvailableItems(itemData.items || []);
      const requestedSkillId = Number(searchParams.get("skill"));
      const requestedItemId = Number(searchParams.get("item"));
      setSelectedCharacterId((currentId) => (
        rows.some((character) => character.id === requestedCharacterId)
          ? requestedCharacterId
          : rows.some((character) => character.id === currentId)
            ? currentId
            : rows[0]?.id || null
      ));
      setSelectedSkillId((currentId) => (
        (skillData.skills || []).some((skill) => skill.id === requestedSkillId)
          ? requestedSkillId
          : (skillData.skills || []).some((skill) => skill.id === currentId)
            ? currentId
          : skillData.skills?.[0]?.id || null
      ));
      setSelectedItemId((currentId) => (
        (itemData.items || []).some((item) => item.id === requestedItemId)
          ? requestedItemId
          : (itemData.items || []).some((item) => item.id === currentId)
            ? currentId
            : itemData.items?.[0]?.id || null
      ));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setIsLoading(false);
    }
  }

  React.useEffect(() => {
    if (!isDataBackedEntity(activeEntity)) {
      setIsLoading(false);
      return;
    }

    if (characters.length || availableSkills.length || availableItems.length) {
      setIsLoading(false);
      return;
    }

    loadCharacters();
  }, [activeEntity, availableItems.length, availableSkills.length, characters.length, novel?.id]);

  React.useEffect(() => {
    const requestedEntity = searchParams.get("entity");

    if (isKnownEntity(requestedEntity) && requestedEntity !== activeEntity) {
      setActiveEntity(requestedEntity);
    }
  }, [queryString]);

  React.useEffect(() => {
    const requestedSection = searchParams.get("section");
    const sections = sectionsForEntity(activeEntity);

    if (sections.some((section) => section.id === requestedSection)) {
      if (requestedSection !== activeSection) {
        setActiveSection(requestedSection);
      }
    } else if (activeSection !== "basic") {
      setActiveSection("basic");
    }
  }, [activeEntity, queryString]);

  React.useEffect(() => {
    if (activeEntity !== "characters") {
      return;
    }

    if (skipNextUrlSelectionSyncRef.current) {
      skipNextUrlSelectionSyncRef.current = false;
      return;
    }

    const requestedCharacterId = Number(searchParams.get("character"));

    if (requestedCharacterId && characters.some((character) => character.id === requestedCharacterId)) {
      setSelectedCharacterId(requestedCharacterId);
    }
  }, [activeEntity, characters, queryString]);

  React.useEffect(() => {
    if (activeEntity !== "skills") {
      return;
    }

    if (skipNextUrlSelectionSyncRef.current) {
      skipNextUrlSelectionSyncRef.current = false;
      return;
    }

    const requestedSkillId = Number(searchParams.get("skill"));

    if (requestedSkillId && availableSkills.some((skill) => skill.id === requestedSkillId)) {
      setSelectedSkillId(requestedSkillId);
    }
  }, [activeEntity, availableSkills, queryString]);

  React.useEffect(() => {
    if (activeEntity !== "items") {
      return;
    }

    if (skipNextUrlSelectionSyncRef.current) {
      skipNextUrlSelectionSyncRef.current = false;
      return;
    }

    const requestedItemId = Number(searchParams.get("item"));

    if (requestedItemId && availableItems.some((item) => item.id === requestedItemId)) {
      setSelectedItemId(requestedItemId);
    }
  }, [activeEntity, availableItems, queryString]);

  React.useEffect(() => {
    const nextParams = new URLSearchParams(queryString);
    let changed = false;

    if (activeEntity && nextParams.get("entity") !== activeEntity) {
      nextParams.set("entity", activeEntity);
      changed = true;
    }

    if (activeSection && nextParams.get("section") !== activeSection) {
      nextParams.set("section", activeSection);
      changed = true;
    }

    if (activeEntity === "characters") {
      if (selectedCharacterId && nextParams.get("character") !== String(selectedCharacterId)) {
        nextParams.set("character", String(selectedCharacterId));
        changed = true;
      }

      if (nextParams.has("skill")) {
        nextParams.delete("skill");
        changed = true;
      }

      if (nextParams.has("item")) {
        nextParams.delete("item");
        changed = true;
      }
    } else if (activeEntity === "skills") {
      if (selectedSkillId && nextParams.get("skill") !== String(selectedSkillId)) {
        nextParams.set("skill", String(selectedSkillId));
        changed = true;
      }

      if (nextParams.has("character")) {
        nextParams.delete("character");
        changed = true;
      }

      if (nextParams.has("item")) {
        nextParams.delete("item");
        changed = true;
      }
    } else if (activeEntity === "items") {
      if (selectedItemId && nextParams.get("item") !== String(selectedItemId)) {
        nextParams.set("item", String(selectedItemId));
        changed = true;
      }

      if (nextParams.has("character")) {
        nextParams.delete("character");
        changed = true;
      }

      if (nextParams.has("skill")) {
        nextParams.delete("skill");
        changed = true;
      }
    } else {
      if (nextParams.has("character")) {
        nextParams.delete("character");
        changed = true;
      }

      if (nextParams.has("skill")) {
        nextParams.delete("skill");
        changed = true;
      }

      if (nextParams.has("item")) {
        nextParams.delete("item");
        changed = true;
      }
    }

    if (changed) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [activeEntity, activeSection, selectedCharacterId, selectedItemId, selectedSkillId, queryString, setSearchParams]);

  function navigateEditorTarget({ characterId = null, entity, itemId = null, section = null, skillId = null }) {
    const target = { characterId, entity, itemId, skillId };
    requestNavigation(target, () => {
      const nextParams = new URLSearchParams(searchParams);
      const nextSection = section || sectionByEntity[entity] || "basic";

      nextParams.set("entity", entity);
      nextParams.set("section", nextSection);

      if (entity === "characters") {
        if (characterId) {
          nextParams.set("character", String(characterId));
        } else {
          nextParams.delete("character");
        }
        nextParams.delete("skill");
        nextParams.delete("item");
      } else if (entity === "skills") {
        if (skillId) {
          nextParams.set("skill", String(skillId));
        } else {
          nextParams.delete("skill");
        }
        nextParams.delete("character");
        nextParams.delete("item");
      } else if (entity === "items") {
        if (itemId) {
          nextParams.set("item", String(itemId));
        } else {
          nextParams.delete("item");
        }
        nextParams.delete("character");
        nextParams.delete("skill");
      } else {
        nextParams.delete("character");
        nextParams.delete("skill");
        nextParams.delete("item");
      }

      setActiveEntity(entity);
      setActiveSection(nextSection);
      setIsEntityBrowserOpen(false);

      if (characterId) {
        setSelectedCharacterId(Number(characterId));
      }

      if (skillId) {
        setSelectedSkillId(Number(skillId));
      }

      if (itemId) {
        setSelectedItemId(Number(itemId));
      }

      skipNextUrlSelectionSyncRef.current = true;
      setSearchParams(nextParams, { replace: true });
    });
  }

  function selectEditorRecord(record) {
    if (activeEntity === "items") {
      requestNavigation({ entity: "items", itemId: record.id }, () => {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set("entity", "items");
        nextParams.set("section", "basic");
        nextParams.set("item", String(record.id));
        nextParams.delete("character");
        nextParams.delete("skill");

        if (selectedItemId !== record.id) {
          setSectionByEntity((current) => ({ ...current, items: "basic" }));
          setActiveSection("basic");
        }

        setSelectedItemId(record.id);
        setIsEntityBrowserOpen(false);
        skipNextUrlSelectionSyncRef.current = true;
        setSearchParams(nextParams, { replace: true });
      });
      return;
    }

    if (activeEntity === "skills") {
      requestNavigation({ entity: "skills", skillId: record.id }, () => {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set("entity", "skills");
        nextParams.set("section", "basic");
        nextParams.set("skill", String(record.id));
        nextParams.delete("character");
        nextParams.delete("item");

        if (selectedSkillId !== record.id) {
          setSectionByEntity((current) => ({ ...current, skills: "basic" }));
          setActiveSection("basic");
        }

        setSelectedSkillId(record.id);
        setIsEntityBrowserOpen(false);
        skipNextUrlSelectionSyncRef.current = true;
        setSearchParams(nextParams, { replace: true });
      });
      return;
    }

    requestNavigation({ entity: "characters", characterId: record.id }, () => {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("entity", "characters");
      nextParams.set("section", "basic");
      nextParams.set("character", String(record.id));
      nextParams.delete("skill");
      nextParams.delete("item");

      if (selectedCharacterId !== record.id) {
        setSectionByEntity((current) => ({ ...current, characters: "basic" }));
        setActiveSection("basic");
      }

      setSelectedCharacterId(record.id);
      setIsEntityBrowserOpen(false);
      skipNextUrlSelectionSyncRef.current = true;
      setSearchParams(nextParams, { replace: true });
    });
  }

  function cancelPendingNavigation() {
    setPendingNavigation(null);
  }

  function discardPendingNavigation() {
    const navigation = pendingNavigation;

    if (!navigation) {
      return;
    }

    discardCurrentDrafts();
    setPendingNavigation(null);
    navigation.proceed();
  }

  async function savePendingNavigation() {
    const navigation = pendingNavigation;

    if (!navigation) {
      return;
    }

    const isValid = activeEntity === "items"
      ? validateCanonicalItemDrafts()
      : activeEntity === "skills"
        ? validateCanonicalSkillDrafts()
        : validateCharacterDrafts();

    if (!isValid) {
      return;
    }

    const didSave = activeEntity === "items"
      ? await saveCanonicalItem({ skipDraftSync: true })
      : activeEntity === "skills"
        ? await saveCanonicalSkill({ skipDraftSync: true })
        : await saveCharacter({ skipDraftSync: true });

    if (!didSave) {
      return;
    }

    setPendingNavigation(null);
    navigation.proceed();
  }

  function focusEditorTarget(change) {
    window.setTimeout(() => {
      const target = change.editTarget?.field
        ? document.querySelector(`[data-editor-field="${change.editTarget.field}"]`)
        : document.querySelector(`[data-editor-row="${change.editTarget?.clientKey}"]`);

      if (!target) {
        return;
      }

      const focusTarget = target.matches("input, textarea, select, button")
        ? target
        : target.querySelector("input, textarea, select, button");

      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("editor-focus-flash");
      window.setTimeout(() => target.classList.remove("editor-focus-flash"), 1400);
      focusTarget?.focus?.({ preventScroll: true });
    }, 80);
  }

  function handleEditPendingChange(change) {
    setIsConfirmingSave(false);

    const section = change.editTarget?.section || "basic";
    setActiveSection(section);

    if (activeEntity === "characters") {
      if (section === "aliases") {
        setAliasDrafts((current) => current.map((alias) => (
          alias.client_key === change.editTarget?.clientKey ? { ...alias, _deleted: false } : alias
        )));
        setEditingAliasKey(change.editTarget?.clientKey || null);
      } else if (section === "cultivation") {
        setCultivationDrafts((current) => current.map((event) => (
          event.client_key === change.editTarget?.clientKey ? { ...event, _deleted: false } : event
        )));
        setEditingCultivationKey(change.editTarget?.clientKey || null);
      } else if (section === "skills") {
        setSkillDrafts((current) => current.map((relationship) => (
          relationship.client_key === change.editTarget?.clientKey ? { ...relationship, _deleted: false } : relationship
        )));
        setEditingSkillKey(change.editTarget?.clientKey || null);
      }
    } else if (activeEntity === "skills") {
      if (section === "aliases") {
        setSkillAliasDrafts((current) => current.map((alias) => (
          alias.client_key === change.editTarget?.clientKey ? { ...alias, _deleted: false } : alias
        )));
        setEditingSkillAliasKey(change.editTarget?.clientKey || null);
      } else if (section === "characters") {
        setSkillCharacterDrafts((current) => current.map((relationship) => (
          relationship.client_key === change.editTarget?.clientKey ? { ...relationship, _deleted: false } : relationship
        )));
        setEditingSkillCharacterKey(change.editTarget?.clientKey || null);
      }
    } else if (activeEntity === "items") {
      if (section === "characters") {
        setItemCharacterDrafts((current) => current.map((relationship) => (
          relationship.client_key === change.editTarget?.clientKey ? { ...relationship, _deleted: false } : relationship
        )));
        setEditingItemCharacterKey(change.editTarget?.clientKey || null);
      }
    }

    focusEditorTarget(change);
  }

  React.useEffect(() => {
    setDraft(characterToDraft(selectedCharacter));
    setAliasDrafts(aliasesToDrafts(selectedCharacter));
    setEditingAliasKey(null);
    setCultivationDrafts(cultivationEventsToDrafts(selectedCharacter));
    setEditingCultivationKey(null);
    setSkillDrafts(skillRelationshipsToDrafts(selectedCharacter));
    setEditingSkillKey(null);
    setItemDrafts(itemRelationshipsToDrafts(selectedCharacter));
    setEditingItemKey(null);
    setChapterValidity({
      first_mentioned_chapter_id: true,
      first_appeared_chapter_id: true,
    });
  }, [selectedCharacterId]);

  React.useEffect(() => {
    setCanonicalSkillDraft(skillToDraft(selectedCanonicalSkill));
    setSkillAliasDrafts(aliasesToDrafts(selectedCanonicalSkill));
    setEditingSkillAliasKey(null);
    setSkillCharacterDrafts(skillCharacterRelationshipsToDrafts(selectedCanonicalSkill));
    setEditingSkillCharacterKey(null);
    setShowCanonicalSkillValidation(false);
  }, [selectedSkillId]);

  React.useEffect(() => {
    setCanonicalItemDraft(itemToDraft(selectedCanonicalItem));
    setItemCharacterDrafts(itemCharacterRelationshipsToDrafts(selectedCanonicalItem));
    setEditingItemCharacterKey(null);
    setShowCanonicalItemValidation(false);
  }, [selectedItemId]);

  function updateDraft(field, value) {
    if (field === "name") {
      setShowCharacterValidation(false);
    }

    setDraft((current) => ({ ...current, [field]: value }));
  }

  function resetCharacterDrafts() {
    setDraft(characterToDraft(selectedCharacter));
    setAliasDrafts(aliasesToDrafts(selectedCharacter));
    setEditingAliasKey(null);
    setCultivationDrafts(cultivationEventsToDrafts(selectedCharacter));
    setEditingCultivationKey(null);
    setSkillDrafts(skillRelationshipsToDrafts(selectedCharacter));
    setEditingSkillKey(null);
    setItemDrafts(itemRelationshipsToDrafts(selectedCharacter));
    setEditingItemKey(null);
    setShowCharacterValidation(false);
  }

  function updateAliasDraft(clientKey, nextDraft) {
    setAliasDrafts((current) => current.map((alias) => (
      alias.client_key === clientKey ? nextDraft : alias
    )));
  }

  function addAliasDraft() {
    const clientKey = `new-alias-${Date.now()}`;
    setAliasDrafts((current) => [
      {
        client_key: clientKey,
        alias: "",
        first_seen_chapter_id: "",
        first_seen_chapter: null,
        evidence: "",
        is_primary: false,
        _deleted: false,
      },
      ...current,
    ]);
    setEditingAliasKey(clientKey);
    setActiveSection("aliases");
  }

  function cancelAliasEdit(aliasDraft) {
    if (!aliasDraft.id) {
      setAliasDrafts((current) => current.filter((alias) => alias.client_key !== aliasDraft.client_key));
    } else {
      const originalAlias = selectedCharacter.aliases.find((alias) => alias.id === aliasDraft.id);
      setAliasDrafts((current) => current.map((alias) => (
        alias.client_key === aliasDraft.client_key ? aliasesToDrafts({ aliases: [originalAlias] })[0] : alias
      )));
    }
    setEditingAliasKey(null);
  }

  function setPrimaryAliasDraft(clientKey) {
    setAliasDrafts((current) => current.map((alias) => ({
      ...alias,
      is_primary: !alias._deleted && alias.client_key === clientKey,
    })));
  }

  function markAliasDeleted(aliasDraft) {
    if (!aliasDraft.id) {
      setAliasDrafts((current) => current.filter((alias) => alias.client_key !== aliasDraft.client_key));
      return;
    }

    setAliasDrafts((current) => current.map((alias) => (
      alias.client_key === aliasDraft.client_key ? { ...alias, _deleted: true } : alias
    )));
    setEditingAliasKey(null);
  }

  function requestAliasDelete(aliasDraft) {
    setConfirmDelete({ type: "alias", draft: aliasDraft });
  }

  function updateCultivationDraft(clientKey, nextDraft) {
    setCultivationDrafts((current) => current.map((event) => (
      event.client_key === clientKey ? nextDraft : event
    )));
  }

  function addCultivationDraft() {
    const clientKey = `new-cultivation-${Date.now()}`;
    setCultivationDrafts((current) => [
      {
        client_key: clientKey,
        cultivation_level: "",
        progression_type: "cultivation_level",
        chapter_id: "",
        chapter: null,
        _sort_chapter_number: Number.MAX_SAFE_INTEGER,
        evidence: "",
        notes: "",
        admin_notes: "",
        _deleted: false,
      },
      ...current,
    ]);
    setEditingCultivationKey(clientKey);
    setActiveSection("cultivation");
  }

  function cancelCultivationEdit(eventDraft) {
    if (!eventDraft.id) {
      setCultivationDrafts((current) => current.filter((event) => event.client_key !== eventDraft.client_key));
    } else {
      const originalEvent = selectedCharacter.progression_events.find((event) => event.id === eventDraft.id);
      setCultivationDrafts((current) => current.map((event) => (
        event.client_key === eventDraft.client_key
          ? cultivationEventsToDrafts({ progression_events: [originalEvent] })[0]
          : event
      )));
    }
    setEditingCultivationKey(null);
  }

  function markCultivationDeleted(eventDraft) {
    if (!eventDraft.id) {
      setCultivationDrafts((current) => current.filter((event) => event.client_key !== eventDraft.client_key));
      return;
    }

    setCultivationDrafts((current) => current.map((event) => (
      event.client_key === eventDraft.client_key ? { ...event, _deleted: true } : event
    )));
    setEditingCultivationKey(null);
  }

  function requestCultivationDelete(eventDraft) {
    setConfirmDelete({ type: "cultivation", draft: eventDraft });
  }

  function confirmPendingDelete() {
    if (!confirmDelete) {
      return;
    }

    if (confirmDelete.type === "alias") {
      markAliasDeleted(confirmDelete.draft);
    } else if (confirmDelete.type === "skill_alias") {
      markCanonicalSkillAliasDeleted(confirmDelete.draft);
    } else if (confirmDelete.type === "skill") {
      markSkillDeleted(confirmDelete.draft);
    } else if (confirmDelete.type === "skill_character") {
      markSkillCharacterDeleted(confirmDelete.draft);
    } else if (confirmDelete.type === "item") {
      markItemDeleted(confirmDelete.draft);
    } else if (confirmDelete.type === "item_character") {
      markItemCharacterDeleted(confirmDelete.draft);
    } else {
      markCultivationDeleted(confirmDelete.draft);
    }

    setConfirmDelete(null);
  }

  function finishCultivationEdit(eventDraft) {
    setCultivationDrafts((current) => current.map((event) => (
      event.client_key === eventDraft.client_key
        ? { ...event, _sort_chapter_number: Number(event.chapter?.chapter_number || 0) }
        : event
    )));
    setEditingCultivationKey(null);
  }

  function updateSkillDraft(clientKey, nextDraft) {
    setSkillDrafts((current) => current.map((relationship) => (
      relationship.client_key === clientKey ? nextDraft : relationship
    )));
  }

  function addSkillDraft() {
    const clientKey = `new-skill-relationship-${Date.now()}`;
    setSkillDrafts((current) => [
      {
        client_key: clientKey,
        skill_id: "",
        skill_name: "",
        chapter_id: "",
        chapter: null,
        _sort_chapter_number: Number.MAX_SAFE_INTEGER,
        description: "",
        evidence_text: "",
        admin_notes: "",
        _deleted: false,
      },
      ...current,
    ]);
    setEditingSkillKey(clientKey);
    setActiveSection("skills");
  }

  function cancelSkillEdit(skillDraft) {
    if (!skillDraft.id) {
      setSkillDrafts((current) => current.filter((relationship) => relationship.client_key !== skillDraft.client_key));
    } else {
      const original = selectedCharacter.skills.find((relationship) => relationship.id === skillDraft.id);
      setSkillDrafts((current) => current.map((relationship) => (
        relationship.client_key === skillDraft.client_key
          ? skillRelationshipsToDrafts({ skills: [original] })[0]
          : relationship
      )));
    }
    setEditingSkillKey(null);
  }

  function markSkillDeleted(skillDraft) {
    if (!skillDraft.id) {
      setSkillDrafts((current) => current.filter((relationship) => relationship.client_key !== skillDraft.client_key));
      return;
    }

    setSkillDrafts((current) => current.map((relationship) => (
      relationship.client_key === skillDraft.client_key
        ? { ...relationship, _deleted: true }
        : relationship
    )));
    setEditingSkillKey(null);
  }

  function requestSkillDelete(skillDraft) {
    setConfirmDelete({ type: "skill", draft: skillDraft });
  }

  function finishSkillEdit(skillDraft) {
    setSkillDrafts((current) => current.map((relationship) => (
      relationship.client_key === skillDraft.client_key
        ? { ...relationship, _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0) }
        : relationship
    )));
    setEditingSkillKey(null);
  }

  function updateItemDraft(clientKey, nextDraft) {
    setItemDrafts((current) => current.map((relationship) => (
      relationship.client_key === clientKey ? nextDraft : relationship
    )));
  }

  function addItemDraft() {
    const clientKey = `new-item-relationship-${Date.now()}`;
    setItemDrafts((current) => [
      {
        client_key: clientKey,
        item_id: "",
        item_name: "",
        chapter_id: "",
        chapter: null,
        _sort_chapter_number: Number.MAX_SAFE_INTEGER,
        description: "",
        evidence_text: "",
        admin_notes: "",
        _deleted: false,
      },
      ...current,
    ]);
    setEditingItemKey(clientKey);
    setActiveSection("items");
  }

  function cancelItemEdit(itemDraft) {
    if (!itemDraft.id) {
      setItemDrafts((current) => current.filter((relationship) => relationship.client_key !== itemDraft.client_key));
    } else {
      const original = selectedCharacter.items.find((relationship) => relationship.id === itemDraft.id);
      setItemDrafts((current) => current.map((relationship) => (
        relationship.client_key === itemDraft.client_key
          ? itemRelationshipsToDrafts({ items: [original] })[0]
          : relationship
      )));
    }
    setEditingItemKey(null);
  }

  function markItemDeleted(itemDraft) {
    if (!itemDraft.id) {
      setItemDrafts((current) => current.filter((relationship) => relationship.client_key !== itemDraft.client_key));
      return;
    }

    setItemDrafts((current) => current.map((relationship) => (
      relationship.client_key === itemDraft.client_key
        ? { ...relationship, _deleted: true }
        : relationship
    )));
    setEditingItemKey(null);
  }

  function requestItemDelete(itemDraft) {
    setConfirmDelete({ type: "item", draft: itemDraft });
  }

  function finishItemEdit(itemDraft) {
    setItemDrafts((current) => current.map((relationship) => (
      relationship.client_key === itemDraft.client_key
        ? { ...relationship, _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0) }
        : relationship
    )));
    setEditingItemKey(null);
  }

  function replaceCharacter(updatedCharacter, { skipDraftSync = false } = {}) {
    setCharacters((current) => current.map((character) => (
      character.id === updatedCharacter.id ? updatedCharacter : character
    )));
    setSelectedCharacterId(updatedCharacter.id);
    if (skipDraftSync) {
      return;
    }

    setDraft(characterToDraft(updatedCharacter));
    setAliasDrafts(aliasesToDrafts(updatedCharacter));
    setEditingAliasKey(null);
    setCultivationDrafts(cultivationEventsToDrafts(updatedCharacter));
    setEditingCultivationKey(null);
    setSkillDrafts(skillRelationshipsToDrafts(updatedCharacter));
    setEditingSkillKey(null);
    setItemDrafts(itemRelationshipsToDrafts(updatedCharacter));
    setEditingItemKey(null);
    setShowCharacterValidation(false);
  }

  function validateCharacterDrafts() {
    if (!selectedCharacter) {
      return false;
    }

    if (!draft.name.trim()) {
      setShowCharacterValidation(true);
      return false;
    }

    if (!Object.values(chapterValidity).every(Boolean)) {
      setError("Fix invalid chapter references before saving.");
      return false;
    }

    if (aliasDrafts.some((alias) => !alias._deleted && (!alias.alias.trim() || !alias.first_seen_chapter_id))) {
      setError("Aliases require a name and first mentioned chapter.");
      return false;
    }

    const aliasNames = new Set();
    const hasDuplicateAlias = aliasDrafts.some((alias) => {
      if (alias._deleted) {
        return false;
      }

      const aliasName = alias.alias.trim().toLowerCase();

      if (aliasNames.has(aliasName)) {
        return true;
      }

      aliasNames.add(aliasName);
      return false;
    });

    if (hasDuplicateAlias) {
      setError("A character cannot have the same alias twice.");
      return false;
    }

    if (aliasDrafts.filter((alias) => !alias._deleted && alias.is_primary).length > 1) {
      setError("A character can only have one primary alias.");
      return false;
    }

    if (cultivationDrafts.some((event) => !event._deleted && (!event.cultivation_level.trim() || !event.chapter_id))) {
      setError("Cultivation breakthroughs require a level and chapter.");
      return false;
    }

    if (skillDrafts.some((relationship) => (
      !relationship._deleted
      && (
        !relationship.skill_id
        || !relationship.chapter_id
      )
    ))) {
      setError("Attached skills require a skill and first known chapter.");
      return false;
    }

    const attachedSkillIds = new Set();
    const hasDuplicateSkillRelationship = skillDrafts.some((relationship) => {
      if (relationship._deleted) {
        return false;
      }

      const skillId = String(relationship.skill_id);

      if (attachedSkillIds.has(skillId)) {
        return true;
      }

      attachedSkillIds.add(skillId);
      return false;
    });

    if (hasDuplicateSkillRelationship) {
      setError("A skill can only be attached to a character once.");
      return false;
    }

    if (itemDrafts.some((relationship) => (
      !relationship._deleted
      && (
        !relationship.item_id
        || !relationship.chapter_id
      )
    ))) {
      setError("Attached items require an item and first known chapter.");
      return false;
    }

    const attachedItemIds = new Set();
    const hasDuplicateItemRelationship = itemDrafts.some((relationship) => {
      if (relationship._deleted) {
        return false;
      }

      const itemId = String(relationship.item_id);

      if (attachedItemIds.has(itemId)) {
        return true;
      }

      attachedItemIds.add(itemId);
      return false;
    });

    if (hasDuplicateItemRelationship) {
      setError("An item can only be attached to a character once.");
      return false;
    }

    return true;
  }

  function requestSaveCharacter() {
    if (!characterSaveChanges.length) {
      setError("No changes to save.");
      return;
    }

    if (validateCharacterDrafts()) {
      setIsConfirmingSave(true);
    }
  }

  async function saveCharacter({ skipDraftSync = false } = {}) {
    if (!selectedCharacter) {
      return false;
    }

    setIsSaving(true);
    setError("");
    try {
      const updatedCharacter = await fetchJson(`${API_BASE_URL}/admin/review/wiki-data/characters/${selectedCharacter.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...normalizePayload(draft),
          aliases: aliasDrafts.map(({ client_key, first_seen_chapter, ...alias }) => alias),
          cultivation_events: cultivationDrafts.map(({ client_key, chapter, _sort_chapter_number, ...event }) => event),
          skill_relationships: skillDrafts.map(({ client_key, chapter, skill_name, _sort_chapter_number, ...relationship }) => relationship),
          item_relationships: itemDrafts.map(({ client_key, chapter, item_name, _sort_chapter_number, ...relationship }) => relationship),
        }),
      });
      replaceCharacter(updatedCharacter, { skipDraftSync });
      setIsConfirmingSave(false);
      return true;
    } catch (saveError) {
      setIsConfirmingSave(false);
      setError(saveError.message);
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function resetCanonicalSkillDrafts() {
    setCanonicalSkillDraft(skillToDraft(selectedCanonicalSkill));
    setSkillAliasDrafts(aliasesToDrafts(selectedCanonicalSkill));
    setEditingSkillAliasKey(null);
    setSkillCharacterDrafts(skillCharacterRelationshipsToDrafts(selectedCanonicalSkill));
    setEditingSkillCharacterKey(null);
    setShowCanonicalSkillValidation(false);
  }

  function updateCanonicalSkillAliasDraft(clientKey, nextDraft) {
    setSkillAliasDrafts((current) => current.map((alias) => (
      alias.client_key === clientKey ? nextDraft : alias
    )));
  }

  function addCanonicalSkillAliasDraft() {
    const clientKey = `new-skill-alias-${Date.now()}`;
    setSkillAliasDrafts((current) => [{
      client_key: clientKey,
      alias: "",
      first_seen_chapter_id: "",
      first_seen_chapter: null,
      evidence: "",
      _deleted: false,
    }, ...current]);
    setEditingSkillAliasKey(clientKey);
    setActiveSection("aliases");
  }

  function cancelCanonicalSkillAliasEdit(aliasDraft) {
    if (!aliasDraft.id) {
      setSkillAliasDrafts((current) => current.filter((alias) => alias.client_key !== aliasDraft.client_key));
    } else {
      const originalAlias = selectedCanonicalSkill.aliases.find((alias) => alias.id === aliasDraft.id);
      setSkillAliasDrafts((current) => current.map((alias) => (
        alias.client_key === aliasDraft.client_key ? aliasesToDrafts({ aliases: [originalAlias] })[0] : alias
      )));
    }
    setEditingSkillAliasKey(null);
  }

  function updateSkillCharacterDraft(clientKey, nextDraft) {
    setSkillCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === clientKey ? nextDraft : relationship
    )));
  }

  function addSkillCharacterDraft() {
    const clientKey = `new-skill-character-${Date.now()}`;
    setSkillCharacterDrafts((current) => [
      {
        client_key: clientKey,
        character_id: "",
        character_name: "",
        chapter_id: "",
        chapter: null,
        _sort_chapter_number: Number.MAX_SAFE_INTEGER,
        description: "",
        evidence_text: "",
        admin_notes: "",
        _deleted: false,
      },
      ...current,
    ]);
    setEditingSkillCharacterKey(clientKey);
    setActiveSection("characters");
  }

  function cancelSkillCharacterEdit(characterDraft) {
    if (!characterDraft.id) {
      setSkillCharacterDrafts((current) => current.filter((relationship) => (
        relationship.client_key !== characterDraft.client_key
      )));
    } else {
      const original = selectedCanonicalSkill.characters.find((relationship) => relationship.id === characterDraft.id);
      setSkillCharacterDrafts((current) => current.map((relationship) => (
        relationship.client_key === characterDraft.client_key
          ? skillCharacterRelationshipsToDrafts({ characters: [original] })[0]
          : relationship
      )));
    }
    setEditingSkillCharacterKey(null);
  }

  function markSkillCharacterDeleted(characterDraft) {
    if (!characterDraft.id) {
      setSkillCharacterDrafts((current) => current.filter((relationship) => (
        relationship.client_key !== characterDraft.client_key
      )));
      return;
    }

    setSkillCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === characterDraft.client_key
        ? { ...relationship, _deleted: true }
        : relationship
    )));
    setEditingSkillCharacterKey(null);
  }

  function requestSkillCharacterDelete(characterDraft) {
    setConfirmDelete({ type: "skill_character", draft: characterDraft });
  }

  function finishSkillCharacterEdit(characterDraft) {
    setSkillCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === characterDraft.client_key
        ? { ...relationship, _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0) }
        : relationship
    )));
    setEditingSkillCharacterKey(null);
  }

  function markCanonicalSkillAliasDeleted(aliasDraft) {
    if (!aliasDraft.id) {
      setSkillAliasDrafts((current) => current.filter((alias) => alias.client_key !== aliasDraft.client_key));
    } else {
      setSkillAliasDrafts((current) => current.map((alias) => (
        alias.client_key === aliasDraft.client_key ? { ...alias, _deleted: true } : alias
      )));
    }
    setEditingSkillAliasKey(null);
  }

  function validateCanonicalSkillDrafts() {
    if (!selectedCanonicalSkill) {
      return false;
    }

    if (!canonicalSkillDraft.name.trim()) {
      setShowCanonicalSkillValidation(true);
      return false;
    }

    if (skillAliasDrafts.some((alias) => !alias._deleted && (!alias.alias.trim() || !alias.first_seen_chapter_id))) {
      setError("Skill aliases require a name and first mentioned chapter.");
      return false;
    }

    const aliasNames = new Set();
    const hasDuplicateAlias = skillAliasDrafts.some((alias) => {
      if (alias._deleted) return false;
      const aliasName = alias.alias.trim().toLowerCase();
      if (aliasNames.has(aliasName)) return true;
      aliasNames.add(aliasName);
      return false;
    });

    if (hasDuplicateAlias) {
      setError("A skill cannot have the same alias twice.");
      return false;
    }

    if (skillCharacterDrafts.some((relationship) => (
      !relationship._deleted
      && (
        !relationship.character_id
        || !relationship.chapter_id
      )
    ))) {
      setError("Attached characters require a character and first known chapter.");
      return false;
    }

    const attachedCharacterIds = new Set();
    const hasDuplicateCharacterRelationship = skillCharacterDrafts.some((relationship) => {
      if (relationship._deleted) {
        return false;
      }

      const characterId = String(relationship.character_id);

      if (attachedCharacterIds.has(characterId)) {
        return true;
      }

      attachedCharacterIds.add(characterId);
      return false;
    });

    if (hasDuplicateCharacterRelationship) {
      setError("A character can only be attached to a skill once.");
      return false;
    }

    return true;
  }

  function requestSaveCanonicalSkill() {
    if (!skillSaveChanges.length) {
      setError("No changes to save.");
      return;
    }

    if (validateCanonicalSkillDrafts()) {
      setIsConfirmingSave(true);
    }
  }

  async function saveCanonicalSkill({ skipDraftSync = false } = {}) {
    if (!selectedCanonicalSkill) return false;

    setIsSaving(true);
    setError("");
    try {
      const updatedSkill = await fetchJson(`${API_BASE_URL}/admin/review/wiki-data/skills/${selectedCanonicalSkill.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...SKILL_FIELDS.reduce((payload, field) => ({
            ...payload,
            [field]: canonicalSkillDraft[field] === "" ? null : canonicalSkillDraft[field],
          }), {}),
          aliases: skillAliasDrafts.map(({ client_key, first_seen_chapter, is_primary, ...alias }) => alias),
          character_relationships: skillCharacterDrafts.map(({ client_key, chapter, character_name, _sort_chapter_number, ...relationship }) => relationship),
        }),
      });
      setAvailableSkills((current) => current.map((skill) => skill.id === updatedSkill.id ? updatedSkill : skill));
      const updatedRelationshipByCharacterId = new Map(
        (updatedSkill.characters || []).map((relationship) => [
          String(relationship.character_id),
          {
            ...relationship,
            skill_id: updatedSkill.id,
            skill_name: updatedSkill.name,
          },
        ])
      );
      setCharacters((current) => current.map((character) => {
        const nextSkills = (character.skills || []).filter((relationship) => (
          String(relationship.skill_id) !== String(updatedSkill.id)
        ));
        const updatedRelationship = updatedRelationshipByCharacterId.get(String(character.id));

        return {
          ...character,
          skills: updatedRelationship ? [...nextSkills, updatedRelationship] : nextSkills,
        };
      }));
      if (!skipDraftSync) {
        setSkillDrafts((current) => {
        const selectedCharacterRelationship = updatedRelationshipByCharacterId.get(String(selectedCharacterId));
        const nextDrafts = current.map((relationship) => (
          String(relationship.skill_id) === String(updatedSkill.id)
            ? { ...relationship, skill_name: updatedSkill.name }
            : relationship
        )).filter((relationship) => {
          if (String(relationship.skill_id) !== String(updatedSkill.id)) {
            return true;
          }

          return Boolean(selectedCharacterRelationship);
        });

        if (
          selectedCharacterRelationship
          && !nextDrafts.some((relationship) => String(relationship.skill_id) === String(updatedSkill.id))
        ) {
          return [
            ...nextDrafts,
            skillRelationshipsToDrafts({ skills: [selectedCharacterRelationship] })[0],
          ];
        }

        return nextDrafts;
      });
        setCanonicalSkillDraft(skillToDraft(updatedSkill));
        setSkillAliasDrafts(aliasesToDrafts(updatedSkill));
        setEditingSkillAliasKey(null);
        setSkillCharacterDrafts(skillCharacterRelationshipsToDrafts(updatedSkill));
        setEditingSkillCharacterKey(null);
      }
      setIsConfirmingSave(false);
      return true;
    } catch (saveError) {
      setIsConfirmingSave(false);
      setError(saveError.message);
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function resetCanonicalItemDrafts() {
    setCanonicalItemDraft(itemToDraft(selectedCanonicalItem));
    setItemCharacterDrafts(itemCharacterRelationshipsToDrafts(selectedCanonicalItem));
    setEditingItemCharacterKey(null);
    setShowCanonicalItemValidation(false);
  }

  function updateItemCharacterDraft(clientKey, nextDraft) {
    setItemCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === clientKey ? nextDraft : relationship
    )));
  }

  function addItemCharacterDraft() {
    const clientKey = `new-item-character-${Date.now()}`;
    setItemCharacterDrafts((current) => [
      {
        client_key: clientKey,
        character_id: "",
        character_name: "",
        chapter_id: "",
        chapter: null,
        _sort_chapter_number: Number.MAX_SAFE_INTEGER,
        description: "",
        evidence_text: "",
        admin_notes: "",
        _deleted: false,
      },
      ...current,
    ]);
    setEditingItemCharacterKey(clientKey);
    setActiveSection("characters");
  }

  function cancelItemCharacterEdit(characterDraft) {
    if (!characterDraft.id) {
      setItemCharacterDrafts((current) => current.filter((relationship) => (
        relationship.client_key !== characterDraft.client_key
      )));
    } else {
      const original = selectedCanonicalItem.characters.find((relationship) => relationship.id === characterDraft.id);
      setItemCharacterDrafts((current) => current.map((relationship) => (
        relationship.client_key === characterDraft.client_key
          ? itemCharacterRelationshipsToDrafts({ characters: [original] })[0]
          : relationship
      )));
    }
    setEditingItemCharacterKey(null);
  }

  function markItemCharacterDeleted(characterDraft) {
    if (!characterDraft.id) {
      setItemCharacterDrafts((current) => current.filter((relationship) => (
        relationship.client_key !== characterDraft.client_key
      )));
      return;
    }

    setItemCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === characterDraft.client_key
        ? { ...relationship, _deleted: true }
        : relationship
    )));
    setEditingItemCharacterKey(null);
  }

  function requestItemCharacterDelete(characterDraft) {
    setConfirmDelete({ type: "item_character", draft: characterDraft });
  }

  function finishItemCharacterEdit(characterDraft) {
    setItemCharacterDrafts((current) => current.map((relationship) => (
      relationship.client_key === characterDraft.client_key
        ? { ...relationship, _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0) }
        : relationship
    )));
    setEditingItemCharacterKey(null);
  }

  function validateCanonicalItemDrafts() {
    if (!selectedCanonicalItem) {
      return false;
    }

    if (!canonicalItemDraft.name.trim()) {
      setShowCanonicalItemValidation(true);
      return false;
    }

    if (itemCharacterDrafts.some((relationship) => (
      !relationship._deleted
      && (
        !relationship.character_id
        || !relationship.chapter_id
      )
    ))) {
      setError("Attached characters require a character and first known chapter.");
      return false;
    }

    const attachedCharacterIds = new Set();
    const hasDuplicateCharacterRelationship = itemCharacterDrafts.some((relationship) => {
      if (relationship._deleted) {
        return false;
      }

      const characterId = String(relationship.character_id);

      if (attachedCharacterIds.has(characterId)) {
        return true;
      }

      attachedCharacterIds.add(characterId);
      return false;
    });

    if (hasDuplicateCharacterRelationship) {
      setError("A character can only be attached to an item once.");
      return false;
    }

    return true;
  }

  function requestSaveCanonicalItem() {
    if (!itemSaveChanges.length) {
      setError("No changes to save.");
      return;
    }

    if (validateCanonicalItemDrafts()) {
      setIsConfirmingSave(true);
    }
  }

  async function saveCanonicalItem({ skipDraftSync = false } = {}) {
    if (!selectedCanonicalItem) return false;

    setIsSaving(true);
    setError("");
    try {
      const updatedItem = await fetchJson(`${API_BASE_URL}/admin/review/wiki-data/items/${selectedCanonicalItem.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...ITEM_FIELDS.reduce((payload, field) => ({
            ...payload,
            [field]: canonicalItemDraft[field] === "" ? null : canonicalItemDraft[field],
          }), {}),
          character_relationships: itemCharacterDrafts.map(({ client_key, chapter, character_name, _sort_chapter_number, ...relationship }) => relationship),
        }),
      });
      setAvailableItems((current) => current.map((item) => item.id === updatedItem.id ? updatedItem : item));
      const updatedRelationshipByCharacterId = new Map(
        (updatedItem.characters || []).map((relationship) => [
          String(relationship.character_id),
          {
            ...relationship,
            item_id: updatedItem.id,
            item_name: updatedItem.name,
          },
        ])
      );
      setCharacters((current) => current.map((character) => {
        const nextItems = (character.items || []).filter((relationship) => (
          String(relationship.item_id) !== String(updatedItem.id)
        ));
        const updatedRelationship = updatedRelationshipByCharacterId.get(String(character.id));

        return {
          ...character,
          items: updatedRelationship ? [...nextItems, updatedRelationship] : nextItems,
        };
      }));
      if (!skipDraftSync) {
        setItemDrafts((current) => {
        const selectedCharacterRelationship = updatedRelationshipByCharacterId.get(String(selectedCharacterId));
        const nextDrafts = current.map((relationship) => (
          String(relationship.item_id) === String(updatedItem.id)
            ? { ...relationship, item_name: updatedItem.name }
            : relationship
        )).filter((relationship) => {
          if (String(relationship.item_id) !== String(updatedItem.id)) {
            return true;
          }

          return Boolean(selectedCharacterRelationship);
        });

        if (
          selectedCharacterRelationship
          && !nextDrafts.some((relationship) => String(relationship.item_id) === String(updatedItem.id))
        ) {
          return [
            ...nextDrafts,
            itemRelationshipsToDrafts({ items: [selectedCharacterRelationship] })[0],
          ];
        }

        return nextDrafts;
      });
        setCanonicalItemDraft(itemToDraft(updatedItem));
        setItemCharacterDrafts(itemCharacterRelationshipsToDrafts(updatedItem));
        setEditingItemCharacterKey(null);
      }
      setIsConfirmingSave(false);
      return true;
    } catch (saveError) {
      setIsConfirmingSave(false);
      setError(saveError.message);
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function renderCharacterEditor() {
    if (isLoading) {
      return <div className="editor-empty-state">Loading characters...</div>;
    }

    if (!characters.length) {
      return <div className="editor-empty-state">No canonical characters yet. Approve records in Review Queue first.</div>;
    }

    if (!selectedCharacter) {
      return <div className="editor-empty-state">Select a character to edit canonical wiki data.</div>;
    }

    const visibleAliasDrafts = aliasDrafts
      .filter((alias) => !alias._deleted)
      .sort((a, b) => {
        if (a.is_primary !== b.is_primary) {
          return a.is_primary ? -1 : 1;
        }

        return Number(a.first_seen_chapter?.chapter_number || 0) - Number(b.first_seen_chapter?.chapter_number || 0);
      });
    const visibleCultivationDrafts = cultivationDrafts
      .filter((event) => !event._deleted)
      .sort((a, b) => Number(b._sort_chapter_number || 0) - Number(a._sort_chapter_number || 0));
    const visibleSkillDrafts = skillDrafts
      .filter((relationship) => !relationship._deleted)
      .sort((a, b) => {
        if (Boolean(a.id) !== Boolean(b.id)) {
          return a.id ? 1 : -1;
        }

        return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
      });
    const visibleItemDrafts = itemDrafts
      .filter((relationship) => !relationship._deleted)
      .sort((a, b) => {
        if (Boolean(a.id) !== Boolean(b.id)) {
          return a.id ? 1 : -1;
        }

        return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
      });

    return (
      <>
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
                      novelId={novel?.id}
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
                      novelId={novel?.id}
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
                      novelId={novel?.id}
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
                        novelId={novel?.id}
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
                        novelId={novel?.id}
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
                        novelId={novel?.id}
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
      </>
    );
  }

  function renderCanonicalSkillEditor() {
    if (isLoading) return <div className="editor-empty-state">Loading skills...</div>;
    if (!availableSkills.length) return <div className="editor-empty-state">No canonical skills yet. Approve records in Review Queue first.</div>;
    if (!selectedCanonicalSkill) return <div className="editor-empty-state">Select a skill to edit canonical wiki data.</div>;

    const visibleAliases = skillAliasDrafts.filter((alias) => !alias._deleted);
    const visibleSkillCharacterDrafts = skillCharacterDrafts
      .filter((relationship) => !relationship._deleted)
      .sort((a, b) => {
        if (Boolean(a.id) !== Boolean(b.id)) {
          return a.id ? 1 : -1;
        }

        return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
      });

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
                    novelId={novel?.id}
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
                      novelId={novel?.id}
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

  function renderCanonicalItemEditor() {
    if (isLoading) return <div className="editor-empty-state">Loading items...</div>;
    if (!availableItems.length) return <div className="editor-empty-state">No canonical items yet. Approve records in Review Queue first.</div>;
    if (!selectedCanonicalItem) return <div className="editor-empty-state">Select an item to edit canonical wiki data.</div>;

    const visibleItemCharacterDrafts = itemCharacterDrafts
      .filter((relationship) => !relationship._deleted)
      .sort((a, b) => {
        if (Boolean(a.id) !== Boolean(b.id)) {
          return a.id ? 1 : -1;
        }

        return Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0);
      });

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
                      novelId={novel?.id}
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

  const activeTab = ENTITY_TABS.find((tab) => tab.id === activeEntity);
  const activeRecords = activeEntity === "items"
    ? filteredCanonicalItems
    : activeEntity === "skills"
      ? filteredCanonicalSkills
      : filteredCharacters;
  const activeRecordCountLabel = activeEntity === "items"
    ? `${filteredCanonicalItems.length} items`
    : activeEntity === "skills"
      ? `${filteredCanonicalSkills.length} skills`
      : `${filteredCharacters.length} characters`;
  const activeBrowseLabel = activeEntity === "items"
    ? "Browse Items"
    : activeEntity === "skills"
      ? "Browse Skills"
      : "Browse Characters";
  const activeSearchPlaceholder = activeEntity === "items"
    ? "Search items..."
    : activeEntity === "skills"
      ? "Search skills..."
      : "Search characters...";

  function renderEntityBrowser(className = "") {
    return (
      <aside className={`editor-list-panel admin-panel ${className}`}>
        <div className="editor-browser-header">
          <div>
            <h2>{activeBrowseLabel}</h2>
            <p>{activeRecordCountLabel}</p>
          </div>
          {className.includes("drawer") ? (
            <button
              type="button"
              className="admin-icon-button"
              onClick={() => setIsEntityBrowserOpen(false)}
              aria-label="Close entity browser"
            >
              <X aria-hidden="true" size={16} />
            </button>
          ) : null}
        </div>

        <div className="editor-search-field">
          <Search aria-hidden="true" size={17} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={activeSearchPlaceholder} />
          {search ? (
            <button type="button" onClick={() => setSearch("")} aria-label="Clear search">
              <X aria-hidden="true" size={15} />
            </button>
          ) : null}
        </div>
        {!className.includes("drawer") ? <p className="editor-list-count">{activeRecordCountLabel}</p> : null}

        <div className="editor-record-list">
          {activeRecords.map((record) => (
            <button
              type="button"
              key={record.id}
              className={`editor-record-card ${(activeEntity === "items" ? selectedItemId : activeEntity === "skills" ? selectedSkillId : selectedCharacterId) === record.id ? "active" : ""}`}
              onClick={() => selectEditorRecord(record)}
            >
              <span className="editor-record-avatar">
                {activeEntity === "items" ? <Package aria-hidden="true" size={18} /> : activeEntity === "skills" ? <Sparkles aria-hidden="true" size={18} /> : <BookOpen aria-hidden="true" size={18} />}
              </span>
              <span>
                <strong>{record.name}</strong>
              </span>
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <div className="workspace-page editor-page">
      <header className="workspace-page-header">
        <div>
          <h1>Wiki Data Editor</h1>
          <p>Edit approved wiki data for this novel.</p>
        </div>
        <div className="workspace-header-actions">
          <button type="button" className="admin-secondary-button" onClick={() => window.open(publicWikiPath, "_blank", "noopener,noreferrer")}>
            View Public Wiki
            <ExternalLink aria-hidden="true" size={15} />
          </button>
        </div>
      </header>

      <section className="editor-page-body">
        <nav className="editor-entity-tabs" aria-label="Wiki data entity types">
          {ENTITY_TABS.map(({ id, label, icon: Icon }) => (
            <button
              type="button"
              key={id}
              className={activeEntity === id ? "active" : ""}
              onClick={() => navigateEditorTarget({
                characterId: id === "characters" ? selectedCharacterId : null,
                entity: id,
                itemId: id === "items" ? selectedItemId : null,
                skillId: id === "skills" ? selectedSkillId : null,
              })}
            >
              <Icon aria-hidden="true" size={16} />
              {label}
            </button>
          ))}
        </nav>

        {!["characters", "skills", "items"].includes(activeEntity) ? (
          <section className="editor-coming-soon admin-panel">
            <div className="editor-coming-icon">
              {activeTab?.icon ? React.createElement(activeTab.icon, { "aria-hidden": true, size: 24 }) : <FileText aria-hidden="true" size={24} />}
            </div>
            <h2>{activeTab?.label} editor is coming soon</h2>
            <p>This page is structured for canonical wiki editing. Characters are implemented first; this section will use the same pattern when the backend editor surface is added.</p>
          </section>
        ) : (
          <>
            <div className="editor-browser-trigger-row">
              <button type="button" className="admin-secondary-button" onClick={() => setIsEntityBrowserOpen(true)}>
                <Search aria-hidden="true" size={16} />
                {activeBrowseLabel}
              </button>
            </div>

            <div className="editor-layout">
              {renderEntityBrowser("desktop")}

              {activeEntity === "items" ? renderCanonicalItemEditor() : activeEntity === "skills" ? renderCanonicalSkillEditor() : renderCharacterEditor()}
            </div>

            {isEntityBrowserOpen ? (
              <div className="editor-browser-backdrop" role="presentation" onMouseDown={() => setIsEntityBrowserOpen(false)}>
                <div className="editor-browser-drawer" role="dialog" aria-modal="true" aria-label={activeBrowseLabel} onMouseDown={(event) => event.stopPropagation()}>
                  {renderEntityBrowser("drawer")}
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>

      <AdminNoticeModal
        title="Wiki Data Editor"
        message={error}
        onClose={() => setError("")}
      />
      <EditorConfirmModal
        action={confirmDelete}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={confirmPendingDelete}
      />
      <EditorConfirmModal
        action={isConfirmingSave ? {
          type: "save",
          changes: activeEntity === "items" ? itemSaveChanges : activeEntity === "skills" ? skillSaveChanges : characterSaveChanges,
          draft: activeEntity === "items" ? selectedCanonicalItem : activeEntity === "skills" ? selectedCanonicalSkill : selectedCharacter,
        } : null}
        onCancel={() => setIsConfirmingSave(false)}
        onEditChange={handleEditPendingChange}
        onConfirm={activeEntity === "items" ? saveCanonicalItem : activeEntity === "skills" ? saveCanonicalSkill : saveCharacter}
      />
      <EditorUnsavedChangesModal
        action={pendingNavigation}
        isSaving={isSaving}
        onCancel={cancelPendingNavigation}
        onDiscard={discardPendingNavigation}
        onSave={savePendingNavigation}
      />
    </div>
  );
}
