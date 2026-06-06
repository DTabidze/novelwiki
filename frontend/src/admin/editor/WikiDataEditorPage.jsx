import React from "react";
import { useSearchParams } from "react-router-dom";
import {
  ExternalLink,
  FileText,
  Search,
  X,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";
import AdminNoticeModal from "../components/AdminNoticeModal.jsx";
import CharacterEditor from "./components/CharacterEditor.jsx";
import { EditorConfirmModal, EditorUnsavedChangesModal } from "./components/EditorModals.jsx";
import ItemEditor from "./components/ItemEditor.jsx";
import SkillEditor from "./components/SkillEditor.jsx";
import {
  aliasesToDrafts,
  CHARACTER_FIELDS,
  characterToDraft,
  cultivationEventsToDrafts,
  emptyDraft,
  getCharacterSubtitle,
  ITEM_FIELDS,
  itemCharacterRelationshipsToDrafts,
  itemRelationshipsToDrafts,
  itemToDraft,
  normalizePayload,
  skillCharacterRelationshipsToDrafts,
  SKILL_FIELDS,
  skillRelationshipsToDrafts,
  skillToDraft,
} from "./editorDrafts.js";
import {
  BROWSE_ICONS,
  CHARACTER_FIELD_LABELS,
  ENTITY_TABS,
  initialEntityFromParams,
  initialSectionFromParams,
  isDataBackedEntity,
  isKnownEntity,
  ITEM_FIELD_LABELS,
  sectionsForEntity,
  SKILL_FIELD_LABELS,
} from "./editorConfig.js";
import {
  summarizeAliasChanges,
  summarizeFieldChanges,
  summarizeRelationshipChanges,
} from "./editorChangeSummary.js";


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
      changes: activeSaveChanges,
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
  const ActiveBrowseIcon = BROWSE_ICONS[activeEntity] || FileText;

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
                <ActiveBrowseIcon aria-hidden="true" size={18} />
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

              {activeEntity === "items" ? (
                <ItemEditor
                  activeSection={activeSection}
                  addItemCharacterDraft={addItemCharacterDraft}
                  availableItems={availableItems}
                  canonicalItemDraft={canonicalItemDraft}
                  cancelItemCharacterEdit={cancelItemCharacterEdit}
                  characters={characters}
                  editingItemCharacterKey={editingItemCharacterKey}
                  finishItemCharacterEdit={finishItemCharacterEdit}
                  isLoading={isLoading}
                  isSaving={isSaving}
                  itemCharacterDrafts={itemCharacterDrafts}
                  navigateEditorTarget={navigateEditorTarget}
                  novelId={novel?.id}
                  requestItemCharacterDelete={requestItemCharacterDelete}
                  requestSaveCanonicalItem={requestSaveCanonicalItem}
                  resetCanonicalItemDrafts={resetCanonicalItemDrafts}
                  selectedCanonicalItem={selectedCanonicalItem}
                  setActiveSection={setActiveSection}
                  setCanonicalItemDraft={setCanonicalItemDraft}
                  setEditingItemCharacterKey={setEditingItemCharacterKey}
                  setShowCanonicalItemValidation={setShowCanonicalItemValidation}
                  showCanonicalItemValidation={showCanonicalItemValidation}
                  updateItemCharacterDraft={updateItemCharacterDraft}
                />
              ) : activeEntity === "skills" ? (
                <SkillEditor
                  activeSection={activeSection}
                  addCanonicalSkillAliasDraft={addCanonicalSkillAliasDraft}
                  addSkillCharacterDraft={addSkillCharacterDraft}
                  availableSkills={availableSkills}
                  cancelCanonicalSkillAliasEdit={cancelCanonicalSkillAliasEdit}
                  cancelSkillCharacterEdit={cancelSkillCharacterEdit}
                  canonicalSkillDraft={canonicalSkillDraft}
                  characters={characters}
                  editingSkillAliasKey={editingSkillAliasKey}
                  editingSkillCharacterKey={editingSkillCharacterKey}
                  finishSkillCharacterEdit={finishSkillCharacterEdit}
                  isLoading={isLoading}
                  isSaving={isSaving}
                  navigateEditorTarget={navigateEditorTarget}
                  novelId={novel?.id}
                  requestSaveCanonicalSkill={requestSaveCanonicalSkill}
                  requestSkillCharacterDelete={requestSkillCharacterDelete}
                  resetCanonicalSkillDrafts={resetCanonicalSkillDrafts}
                  selectedCanonicalSkill={selectedCanonicalSkill}
                  setActiveSection={setActiveSection}
                  setCanonicalSkillDraft={setCanonicalSkillDraft}
                  setConfirmDelete={setConfirmDelete}
                  setEditingSkillAliasKey={setEditingSkillAliasKey}
                  setEditingSkillCharacterKey={setEditingSkillCharacterKey}
                  setShowCanonicalSkillValidation={setShowCanonicalSkillValidation}
                  showCanonicalSkillValidation={showCanonicalSkillValidation}
                  skillAliasDrafts={skillAliasDrafts}
                  skillCharacterDrafts={skillCharacterDrafts}
                  updateCanonicalSkillAliasDraft={updateCanonicalSkillAliasDraft}
                  updateSkillCharacterDraft={updateSkillCharacterDraft}
                />
              ) : (
                <CharacterEditor
                  activeSection={activeSection}
                  addAliasDraft={addAliasDraft}
                  addCultivationDraft={addCultivationDraft}
                  addItemDraft={addItemDraft}
                  addSkillDraft={addSkillDraft}
                  aliasDrafts={aliasDrafts}
                  availableItems={availableItems}
                  availableSkills={availableSkills}
                  cancelAliasEdit={cancelAliasEdit}
                  cancelCultivationEdit={cancelCultivationEdit}
                  cancelItemEdit={cancelItemEdit}
                  cancelSkillEdit={cancelSkillEdit}
                  characters={characters}
                  cultivationDrafts={cultivationDrafts}
                  draft={draft}
                  editingAliasKey={editingAliasKey}
                  editingCultivationKey={editingCultivationKey}
                  editingItemKey={editingItemKey}
                  editingSkillKey={editingSkillKey}
                  finishCultivationEdit={finishCultivationEdit}
                  finishItemEdit={finishItemEdit}
                  finishSkillEdit={finishSkillEdit}
                  isLoading={isLoading}
                  isSaving={isSaving}
                  itemDrafts={itemDrafts}
                  navigateEditorTarget={navigateEditorTarget}
                  novelId={novel?.id}
                  requestAliasDelete={requestAliasDelete}
                  requestCultivationDelete={requestCultivationDelete}
                  requestItemDelete={requestItemDelete}
                  requestSaveCharacter={requestSaveCharacter}
                  requestSkillDelete={requestSkillDelete}
                  resetCharacterDrafts={resetCharacterDrafts}
                  selectedCharacter={selectedCharacter}
                  setActiveSection={setActiveSection}
                  setChapterValidity={setChapterValidity}
                  setEditingAliasKey={setEditingAliasKey}
                  setEditingCultivationKey={setEditingCultivationKey}
                  setEditingItemKey={setEditingItemKey}
                  setEditingSkillKey={setEditingSkillKey}
                  setPrimaryAliasDraft={setPrimaryAliasDraft}
                  showCharacterValidation={showCharacterValidation}
                  skillDrafts={skillDrafts}
                  updateAliasDraft={updateAliasDraft}
                  updateCultivationDraft={updateCultivationDraft}
                  updateDraft={updateDraft}
                  updateItemDraft={updateItemDraft}
                  updateSkillDraft={updateSkillDraft}
                />
              )}
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
