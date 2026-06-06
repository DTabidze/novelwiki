import { BookOpen, Package, Sparkles, Timeline, Users } from "lucide-react";

import {
  CHARACTER_SECTIONS,
  ITEM_SECTIONS,
  SKILL_SECTIONS,
} from "./editorDrafts.js";

export const ENTITY_TABS = [
  { id: "characters", label: "Characters", icon: Users, enabled: true },
  { id: "skills", label: "Skills", icon: Sparkles, enabled: true },
  { id: "items", label: "Items", icon: Package, enabled: true },
  { id: "progression", label: "Cultivation", icon: Timeline, enabled: false },
];

export const BROWSE_ICONS = {
  characters: BookOpen,
  items: Package,
  skills: Sparkles,
};

export const CHARACTER_FIELD_LABELS = {
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

export const SKILL_FIELD_LABELS = {
  name: "Canonical name",
  category: "Category",
  description: "Description",
  admin_notes: "Admin notes",
};

export const ITEM_FIELD_LABELS = {
  name: "Canonical name",
  category: "Category",
  description: "Description",
  admin_notes: "Admin notes",
};

export function isKnownEntity(entity) {
  return ENTITY_TABS.some((tab) => tab.id === entity);
}

export function isDataBackedEntity(entity) {
  return ["characters", "skills", "items"].includes(entity);
}

export function sectionsForEntity(entity) {
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

export function initialEntityFromParams(searchParams) {
  const requestedEntity = searchParams.get("entity");
  return isKnownEntity(requestedEntity) ? requestedEntity : "characters";
}

export function initialSectionFromParams(searchParams, entity) {
  const requestedSection = searchParams.get("section");
  const sections = sectionsForEntity(entity);
  return sections.some((section) => section.id === requestedSection) ? requestedSection : "basic";
}
