import React from "react";
import { Eye, Info, Pencil, Save, X } from "lucide-react";
import { chapterLabel } from "../../utils/wikiFormat.js";
import {
  confidenceText,
  evidenceRows,
  formatReviewType,
  proposedDataRows,
  recordSummary,
  sourceChapter,
} from "./reviewUtils.js";

const PROGRESSION_TYPES = [
  "cultivation_level",
  "realm",
  "rank",
  "status",
  "skill_mastery",
  "power_change",
  "other",
];

function field(label, name, options = {}) {
  return { label, name, ...options };
}

const EDIT_FIELD_CONFIG = {
  characters: [
    field("Name", "name", { required: true }),
    field("Race / Type", "race_or_species"),
    field("Affiliation", "faction_or_affiliation"),
    field("Gender", "gender"),
    field("Status", "status"),
    field("Origin", "origin"),
    field("Age", "age_text"),
    field("Titles", "titles", { multiline: true }),
    field("Description", "description", { multiline: true }),
  ],
  character_metadata_proposals: [
    field("Character", "character_name", { readOnly: true }),
    field("Field", "field_name", { readOnly: true }),
    field("Old value", "old_value", { readOnly: true }),
    field("Proposed value", "proposed_value", { required: true, multiline: true }),
  ],
  progression_events: [
    field("Character", "character_name", { readOnly: true }),
    field("Progression Type", "progression_type", { required: true, options: PROGRESSION_TYPES }),
    field("Old Value", "old_value"),
    field("New Value", "new_value", { required: true }),
    field("Description", "description", { multiline: true }),
  ],
  skills: [
    field("Name", "name", { required: true }),
    field("Category", "category"),
    field("Description", "description", { multiline: true }),
  ],
  items: [
    field("Name", "name", { required: true }),
    field("Category", "category"),
    field("Description", "description", { multiline: true }),
  ],
  character_skills: [
    field("Character", "character_name", { readOnly: true }),
    field("Skill", "skill_name", { readOnly: true }),
    field("Description", "description", { multiline: true }),
  ],
  character_items: [
    field("Character", "character_name", { readOnly: true }),
    field("Item", "item_name", { readOnly: true }),
    field("Relationship", "relationship_type", { required: true }),
    field("Description", "description", { multiline: true }),
  ],
  life_events: [
    field("Character", "character_name", { readOnly: true }),
    field("Event Type", "event_type", { required: true }),
    field("Description", "description", { required: true, multiline: true }),
    field("Reason", "reason", { multiline: true }),
  ],
  events: [
    field("Event Type", "event_type", { required: true }),
    field("Title", "title", { required: true }),
    field("Description", "description", { multiline: true }),
  ],
};

function editableFieldsFor(item) {
  return EDIT_FIELD_CONFIG[item?.entityType] || proposedDataRows(item).map(([label]) => field(label, label));
}

function editablePayload(fields, formValues) {
  return fields.reduce((payload, config) => {
    if (!config.readOnly && config.name) {
      payload[config.name] = formValues[config.name] ?? "";
    }
    return payload;
  }, {});
}

function initialValues(item, fields) {
  const values = {};
  fields.forEach((config) => {
    values[config.name] = item?.[config.name] ?? "";
  });
  values.admin_notes = item?.admin_notes ?? "";
  return values;
}

function validate(fields, values) {
  const missingField = fields.find(
    (config) => config.required && !config.readOnly && !String(values[config.name] || "").trim()
  );

  if (missingField) {
    return `${missingField.label} is required.`;
  }

  return "";
}

function FieldControl({ config, value, onChange }) {
  const id = `review-edit-${config.name}`;

  if (config.options) {
    return (
      <select
        id={id}
        className="admin-select"
        value={value}
        disabled={config.readOnly}
        onChange={(event) => onChange(config.name, event.target.value)}
      >
        {config.options.map((option) => (
          <option value={option} key={option}>{option}</option>
        ))}
      </select>
    );
  }

  if (config.multiline) {
    return (
      <textarea
        id={id}
        className="admin-textarea"
        value={value}
        disabled={config.readOnly}
        rows={config.readOnly ? 2 : 4}
        onChange={(event) => onChange(config.name, event.target.value)}
      />
    );
  }

  return (
    <input
      id={id}
      className="admin-input"
      value={value}
      disabled={config.readOnly}
      onChange={(event) => onChange(config.name, event.target.value)}
    />
  );
}

export default function ReviewEditProposalModal({
  item,
  isSaving,
  error,
  onClose,
  onSave,
  onViewContext,
}) {
  const fields = React.useMemo(() => editableFieldsFor(item), [item]);
  const [values, setValues] = React.useState(() => initialValues(item, fields));
  const [validationError, setValidationError] = React.useState("");
  const chapter = sourceChapter(item);
  const evidence = evidenceRows(item);
  const typeLabel = formatReviewType(item.entityType);

  React.useEffect(() => {
    setValues(initialValues(item, fields));
    setValidationError("");
  }, [fields, item]);

  React.useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  function updateValue(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    const nextValidationError = validate(fields, values);
    setValidationError(nextValidationError);

    if (nextValidationError) return;

    await onSave({
      ...editablePayload(fields, values),
      admin_notes: values.admin_notes || "",
    });
  }

  return (
    <div className="review-edit-backdrop" role="presentation" onMouseDown={onClose}>
      <form
        className="review-edit-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-edit-title"
        onMouseDown={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <header className="review-edit-header">
          <div className="review-edit-heading">
            <span className="review-edit-icon"><Pencil aria-hidden="true" size={20} /></span>
            <div>
              <h2 id="review-edit-title">Edit {typeLabel} Proposal</h2>
              <p>Update the proposed data for this review item.</p>
            </div>
          </div>
          <button type="button" className="admin-icon-button" onClick={onClose} aria-label="Close edit modal">
            <X size={18} />
          </button>
        </header>

        <div className="review-edit-body">
          <section className="review-edit-summary" aria-label="Review item context">
            <div>
              <span>Review Item</span>
              <strong className={`review-type-chip ${item.typeGroup}`}>{typeLabel}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong className={`review-status-badge ${item.review_status}`}>{item.review_status}</strong>
            </div>
            <div>
              <span>Chapter</span>
              <strong className="review-chapter-chip">{chapterLabel(chapter)}</strong>
            </div>
            <div>
              <span>Confidence</span>
              <strong>{confidenceText(item)}</strong>
            </div>
          </section>

          <section className="review-edit-section">
            <h3>Proposed Data</h3>
            <div className="review-edit-form-table">
              {fields.map((config) => (
                <label key={config.name} htmlFor={`review-edit-${config.name}`}>
                  <span>
                    {config.label}
                    {config.required ? <em>*</em> : null}
                  </span>
                  <FieldControl config={config} value={values[config.name] ?? ""} onChange={updateValue} />
                </label>
              ))}
            </div>
          </section>

          <section className="review-edit-section">
            <h3>Evidence <span>(read-only)</span></h3>
            {evidence.length === 0 ? (
              <p className="admin-muted">No evidence snippet was attached to this item.</p>
            ) : (
              evidence.slice(0, 2).map((row) => (
                <blockquote className="review-edit-evidence" key={row.id || row.evidence_text}>
                  <p>{row.evidence_text}</p>
                  <footer>
                    <span>{chapterLabel(chapter)}</span>
                    <button type="button" className="admin-secondary-button" onClick={() => onViewContext?.(row)}>
                      <Eye size={15} /> View Full Context
                    </button>
                  </footer>
                </blockquote>
              ))
            )}
          </section>

          <section className="review-edit-section">
            <h3>AI Notes <span>(read-only)</span></h3>
            <div className="review-edit-readonly-note">
              <Info size={16} />
              <p>{item.extraction_reason || recordSummary(item)}</p>
            </div>
          </section>

          <section className="review-edit-section">
            <label className="review-edit-notes-label" htmlFor="reviewer-notes">
              Reviewer Notes <span>(optional)</span>
            </label>
            <textarea
              id="reviewer-notes"
              className="admin-textarea"
              value={values.admin_notes}
              placeholder="Add notes about this edit..."
              rows={4}
              onChange={(event) => updateValue("admin_notes", event.target.value)}
            />
          </section>

          {(validationError || error) && (
            <div className="review-edit-error" role="alert">
              {validationError || error}
            </div>
          )}
        </div>

        <footer className="review-edit-footer">
          <button type="button" className="admin-secondary-button" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button type="submit" disabled={isSaving}>
            <Save size={16} /> {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </footer>
      </form>
    </div>
  );
}
