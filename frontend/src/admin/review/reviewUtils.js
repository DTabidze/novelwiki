export const REVIEW_ENTITY_TYPES = [
  "characters",
  "character_metadata_proposals",
  "progression_events",
  "skills",
  "items",
  "character_skills",
  "character_items",
  "life_events",
  "events",
];

export const REVIEW_TYPE_GROUPS = {
  characters: "characters",
  character_metadata_proposals: "metadata",
  progression_events: "progression",
  skills: "skills_items",
  items: "skills_items",
  character_skills: "skills_items",
  character_items: "skills_items",
  life_events: "progression",
  events: "progression",
};

export const REVIEW_TYPE_LABELS = {
  characters: "Character",
  character_metadata_proposals: "Metadata",
  progression_events: "Progression",
  skills: "Skill",
  items: "Item",
  character_skills: "Skill Link",
  character_items: "Item Link",
  life_events: "Life Event",
  events: "Event",
};

export function formatReviewType(entityType) {
  return REVIEW_TYPE_LABELS[entityType] || "Review Item";
}

export function confidenceLevel(record) {
  const score = Number(record.confidence_score);

  if (!Number.isFinite(score)) {
    return "medium";
  }

  if (score >= 0.8) return "high";
  if (score >= 0.55) return "medium";
  return "low";
}

export function confidenceText(record) {
  const level = confidenceLevel(record);
  return `${level.slice(0, 1).toUpperCase()}${level.slice(1)}`;
}

export function reviewWarnings(record) {
  return Array.isArray(record.review_warnings) ? record.review_warnings : [];
}

export function sourceChapter(record) {
  return record.source_chapter || record.chapter || null;
}

export function recordKey(item) {
  return `${item.entityType}:${item.id}`;
}

export function isAssumedSpeciesOverride(record) {
  return (
    record.entityType === "character_metadata_proposals"
    && record.field_name === "race_or_species"
    && (record.old_value || "").toLowerCase() === "human"
    && (record.proposed_value || "").toLowerCase() !== "human"
  );
}

export function reviewTitle(record) {
  if (isAssumedSpeciesOverride(record)) {
    return `Override assumed species: ${record.old_value || "Human"} -> ${record.proposed_value}`;
  }

  switch (record.entityType) {
    case "characters":
      return `New Character: ${record.name || "Unnamed character"}`;
    case "character_metadata_proposals":
      return `${record.character_name || "Character"}: ${record.field_name || "metadata"} -> ${record.proposed_value}`;
    case "progression_events":
      return `${record.character_name || "Character"}: ${record.new_value || record.progression_type || "Progression update"}`;
    case "character_skills":
      return `${record.character_name || "Character"}: ${record.skill_name || "Skill"} ${record.relationship_type || ""}`.trim();
    case "character_items":
      return `${record.character_name || "Character"}: ${record.item_name || "Item"} ${record.relationship_type || ""}`.trim();
    case "skills":
      return `Skill: ${record.name || "Unnamed skill"}`;
    case "items":
      return `Item: ${record.name || "Unnamed item"}`;
    case "life_events":
      return `${record.character_name || "Character"}: ${record.event_type || "Life event"}`;
    case "events":
      return record.title || "Wiki event";
    default:
      return record.name || record.title || "Review item";
  }
}

export function recordSummary(record) {
  switch (record.entityType) {
    case "characters":
      return record.description || record.race_or_species || "Character proposal";
    case "character_metadata_proposals":
      return record.extraction_reason || record.evidence_text || "Metadata proposal";
    case "progression_events":
      return record.description || "Progression proposal";
    case "character_skills":
      return record.description || "Character skill relationship";
    case "character_items":
      return record.description || "Character item relationship";
    case "skills":
    case "items":
      return record.description || record.category || "Extracted wiki data";
    case "life_events":
      return record.reason || record.description || "Character life event";
    case "events":
      return record.description || "Wiki event";
    default:
      return "Review item";
  }
}

export function flattenReviewData(extractedData) {
  return REVIEW_ENTITY_TYPES.flatMap((entityType) =>
    (extractedData?.[entityType] || []).map((record) => ({
      ...record,
      entityType,
      typeGroup: REVIEW_TYPE_GROUPS[entityType] || entityType,
    }))
  );
}

export function proposedDataRows(record) {
  if (!record) return [];

  if (record.entityType === "characters") {
    return [
      ["Name", record.name],
      ["Alias", (record.aliases || []).map((alias) => alias.alias).join(", ")],
      ["Race / Type", record.race_or_species],
      ["Affiliation", record.faction_or_affiliation],
      ["Cultivation", record.current_cultivation_level],
      ["Gender", record.gender],
      ["Status", record.status],
      ["Origin", record.origin],
      ["Titles", record.titles],
    ].filter(([, value]) => value);
  }

  if (record.entityType === "character_metadata_proposals") {
    return [
      ["Character", record.character_name],
      ["Field", record.field_name],
      ["Old value", record.old_value || "Empty"],
      ["Proposed value", record.proposed_value],
      ["Raw proposed value", record.raw_proposed_value],
      ["Normalized value", record.normalized_value],
      ["Confidence", Number.isFinite(Number(record.confidence_score)) ? `${Math.round(record.confidence_score * 100)}%` : null],
    ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  }

  if (record.entityType === "progression_events") {
    return [
      ["Character", record.character_name],
      ["Progression type", record.progression_type],
      ["Old value", record.old_value || "Empty"],
      ["New value", record.new_value],
      ["Description", record.description],
    ].filter(([, value]) => value);
  }

  if (record.entityType === "character_skills") {
    return [
      ["Character", record.character_name],
      ["Skill", record.skill_name],
      ["Relationship", record.relationship_type],
      ["Description", record.description],
    ].filter(([, value]) => value);
  }

  if (record.entityType === "character_items") {
    return [
      ["Character", record.character_name],
      ["Item", record.item_name],
      ["Relationship", record.relationship_type],
      ["Description", record.description],
    ].filter(([, value]) => value);
  }

  if (record.entityType === "life_events") {
    return [
      ["Character", record.character_name],
      ["Event type", record.event_type],
      ["Description", record.description],
      ["Reason", record.reason],
    ].filter(([, value]) => value);
  }

  return [
    ["Name", record.name || record.title],
    ["Category / Type", record.category || record.event_type],
    ["Description", record.description],
  ].filter(([, value]) => value);
}

export function evidenceRows(record) {
  const evidence = [];

  if (record?.evidence_text) {
    evidence.push({ id: "inline", evidence_text: record.evidence_text, chapter_id: record.chapter_id });
  }

  if (Array.isArray(record?.evidence)) {
    record.evidence.forEach((row) => evidence.push(row));
  }

  return evidence;
}
