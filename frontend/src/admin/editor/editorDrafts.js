import { chapterLabel } from "../../utils/wikiFormat.js";

export const CHARACTER_FIELDS = [
  "name",
  "description",
  "first_mentioned_chapter_id",
  "first_appeared_chapter_id",
  "first_seen_chapter_id",
  "age_text",
  "gender",
  "race_or_species",
  "race_or_species_source",
  "race_or_species_confidence",
  "origin",
  "faction_or_affiliation",
  "status",
  "titles",
  "current_cultivation_level",
  "current_position",
  "current_class_rank",
  "current_power_rank",
  "admin_notes",
];

export const CHARACTER_SECTIONS = [
  { id: "basic", label: "Basic Info" },
  { id: "aliases", label: "Aliases" },
  { id: "cultivation", label: "Cultivation" },
  { id: "skills", label: "Skills" },
  { id: "items", label: "Items" },
  { id: "evidence", label: "Evidence" },
  { id: "notes", label: "Notes & History" },
];

export const SKILL_FIELDS = ["name", "category", "description", "admin_notes"];

export const SKILL_CATEGORIES = [
  "Technique",
  "Cultivation Method",
  "Divine Ability",
  "Spell",
  "Martial Art",
  "Combat Move",
  "Movement Skill",
  "Body Refinement",
  "Soul Skill",
  "Alchemy",
  "Formation",
  "Utility",
  "Other",
];

const SKILL_CATEGORY_LOOKUP = new Map(SKILL_CATEGORIES.map((category) => [category.toLowerCase(), category]));

export function normalizeSkillCategory(category) {
  const normalizedCategory = String(category || "").trim().replace(/\s+/g, " ").toLowerCase();
  return SKILL_CATEGORY_LOOKUP.get(normalizedCategory) || "";
}

export const SKILL_SECTIONS = [
  { id: "basic", label: "Basic Info" },
  { id: "aliases", label: "Aliases" },
  { id: "characters", label: "Characters" },
  { id: "evidence", label: "Evidence" },
  { id: "notes", label: "Notes" },
];

export const ITEM_FIELDS = ["name", "category", "description", "admin_notes"];

export const ITEM_CATEGORIES = [
  "Manual",
  "Weapon",
  "Artifact",
  "Pill",
  "Treasure",
  "Resource",
  "Medicine",
  "Scroll",
  "Quest Item",
  "Other",
];

const ITEM_CATEGORY_LOOKUP = new Map(ITEM_CATEGORIES.map((category) => [category.toLowerCase(), category]));

export function normalizeItemCategory(category) {
  const normalizedCategory = String(category || "").trim().replace(/_/g, " ").replace(/\s+/g, " ").toLowerCase();
  return ITEM_CATEGORY_LOOKUP.get(normalizedCategory) || "";
}

export const ITEM_SECTIONS = [
  { id: "basic", label: "Basic Info" },
  { id: "characters", label: "Characters" },
  { id: "evidence", label: "Evidence" },
  { id: "notes", label: "Notes" },
];

export function emptyDraft() {
  return CHARACTER_FIELDS.reduce((draft, field) => ({ ...draft, [field]: "" }), {});
}

export function characterToDraft(character) {
  if (!character) {
    return emptyDraft();
  }

  return CHARACTER_FIELDS.reduce((draft, field) => {
    draft[field] = character[field] ?? "";
    return draft;
  }, {});
}

export function normalizePayload(draft) {
  return CHARACTER_FIELDS.reduce((payload, field) => {
    payload[field] = draft[field] === "" ? null : draft[field];
    return payload;
  }, {});
}

export function skillToDraft(skill) {
  return SKILL_FIELDS.reduce((draft, field) => {
    draft[field] = field === "category"
      ? normalizeSkillCategory(skill?.[field])
      : skill?.[field] ?? "";
    return draft;
  }, {});
}

export function itemToDraft(item) {
  return ITEM_FIELDS.reduce((draft, field) => {
    draft[field] = field === "category"
      ? normalizeItemCategory(item?.[field])
      : item?.[field] ?? "";
    return draft;
  }, {});
}

export function formatChapter(chapter) {
  return chapter ? chapterLabel(chapter) : "Not linked";
}

export function getCharacterSubtitle(character) {
  return (
    character.current_position ||
    character.faction_or_affiliation ||
    character.current_cultivation_level ||
    character.status ||
    "Canonical wiki record"
  );
}

export function aliasesToDrafts(record) {
  return (record?.aliases || []).map((alias) => ({
    id: alias.id,
    client_key: `alias-${alias.id}`,
    alias: alias.alias || "",
    first_seen_chapter_id: alias.first_seen_chapter_id || "",
    first_seen_chapter: alias.first_seen_chapter || null,
    evidence: alias.evidence || "",
    is_primary: Boolean(alias.is_primary),
    _deleted: false,
  }));
}

const CULTIVATION_PROGRESSION_TYPES = new Set(["cultivation_level", "realm"]);

export function cultivationEventsToDrafts(character) {
  return (character?.progression_events || [])
    .filter((event) => CULTIVATION_PROGRESSION_TYPES.has(event.progression_type))
    .map((event) => ({
      id: event.id,
      client_key: `cultivation-${event.id}`,
      cultivation_level: event.new_value || "",
      progression_type: event.progression_type || "cultivation_level",
      chapter_id: event.chapter_id || "",
      chapter: event.chapter || null,
      _sort_chapter_number: Number(event.chapter?.chapter_number || 0),
      evidence: event.evidence?.[0]?.evidence_text || "",
      notes: event.description || "",
      admin_notes: event.admin_notes || "",
      _deleted: false,
    }))
    .sort((a, b) => Number(b.chapter?.chapter_number || 0) - Number(a.chapter?.chapter_number || 0));
}

export function skillRelationshipsToDrafts(character) {
  return (character?.skills || [])
    .map((relationship) => ({
      id: relationship.id,
      client_key: `skill-relationship-${relationship.id}`,
      skill_id: relationship.skill_id || "",
      skill_name: relationship.skill_name || "",
      chapter_id: relationship.chapter_id || relationship.source_chapter_id || "",
      chapter: relationship.chapter || null,
      _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0),
      description: relationship.description || "",
      evidence_text: relationship.evidence?.[0]?.evidence_text || "",
      admin_notes: relationship.admin_notes || "",
      _deleted: false,
    }))
    .sort((a, b) => Number(a.chapter?.chapter_number || 0) - Number(b.chapter?.chapter_number || 0));
}

export function skillCharacterRelationshipsToDrafts(skill) {
  return (skill?.characters || [])
    .map((relationship) => ({
      id: relationship.id,
      client_key: `skill-character-${relationship.id}`,
      character_id: relationship.character_id || "",
      character_name: relationship.character_name || "",
      chapter_id: relationship.chapter_id || relationship.source_chapter_id || "",
      chapter: relationship.chapter || null,
      _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0),
      description: relationship.description || "",
      evidence_text: relationship.evidence?.[0]?.evidence_text || "",
      admin_notes: relationship.admin_notes || "",
      _deleted: false,
    }))
    .sort((a, b) => Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0));
}

export function itemRelationshipsToDrafts(character) {
  return (character?.items || [])
    .map((relationship) => ({
      id: relationship.id,
      client_key: `item-relationship-${relationship.id}`,
      item_id: relationship.item_id || "",
      item_name: relationship.item_name || "",
      chapter_id: relationship.chapter_id || relationship.source_chapter_id || "",
      chapter: relationship.chapter || null,
      _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0),
      description: relationship.description || "",
      evidence_text: relationship.evidence?.[0]?.evidence_text || "",
      admin_notes: relationship.admin_notes || "",
      _deleted: false,
    }))
    .sort((a, b) => Number(a.chapter?.chapter_number || 0) - Number(b.chapter?.chapter_number || 0));
}

export function itemCharacterRelationshipsToDrafts(item) {
  return (item?.characters || [])
    .map((relationship) => ({
      id: relationship.id,
      client_key: `item-character-${relationship.id}`,
      character_id: relationship.character_id || "",
      character_name: relationship.character_name || "",
      chapter_id: relationship.chapter_id || relationship.source_chapter_id || "",
      chapter: relationship.chapter || null,
      _sort_chapter_number: Number(relationship.chapter?.chapter_number || 0),
      description: relationship.description || "",
      evidence_text: relationship.evidence?.[0]?.evidence_text || "",
      admin_notes: relationship.admin_notes || "",
      _deleted: false,
    }))
    .sort((a, b) => Number(a._sort_chapter_number || 0) - Number(b._sort_chapter_number || 0));
}
