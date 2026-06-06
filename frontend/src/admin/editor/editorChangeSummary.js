import { aliasesToDrafts, formatChapter } from "./editorDrafts.js";

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

export function summarizeFieldChanges(fields, draft, original, labels, options = {}) {
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

export function summarizeAliasChanges(drafts, originalRecord, label = "alias", section = "aliases", options = {}) {
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

export function summarizeRelationshipChanges(drafts, originalDrafts, entityLabel, getName, section, options = {}) {
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
