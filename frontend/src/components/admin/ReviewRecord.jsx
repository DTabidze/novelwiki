import React from "react";
import { API_BASE_URL, fetchJson } from "../../api.js";

export default function ReviewRecord({ entityType, record, fields, mergeTargets = [], onMerged, onSaved }) {
  const [formValues, setFormValues] = React.useState(() => {
    const values = {};

    fields.forEach((field) => {
      values[field] = record[field] || "";
    });

    values.admin_notes = record.admin_notes || "";
    return values;
  });
  const [isSaving, setIsSaving] = React.useState(false);
  const [mergeTargetId, setMergeTargetId] = React.useState("");

  async function saveRecord(extraValues = {}) {
    setIsSaving(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/review/${entityType}/${record.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...formValues,
          ...extraValues,
        }),
      });

      onSaved(data);
    } finally {
      setIsSaving(false);
    }
  }

  async function mergeCharacter() {
    if (!mergeTargetId) {
      return;
    }

    setIsSaving(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/review/characters/${record.id}/merge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_character_id: Number(mergeTargetId),
        }),
      });

      onMerged(record.id, data);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <article className="mini-record review-record">
      <div className="record-title-row">
        <strong>
          {record.name ||
            record.title ||
            record.new_value ||
            record.character_name ||
            record.entity_type ||
            entityType}
        </strong>
        <span className={`status-pill ${record.review_status}`}>{record.review_status}</span>
      </div>

      {record.character_name && entityType !== "characters" ? (
        <p className="source-line">Character: {record.character_name}</p>
      ) : null}

      {record.skill_name ? <p className="source-line">Skill: {record.skill_name}</p> : null}
      {record.item_name ? <p className="source-line">Item: {record.item_name}</p> : null}

      {record.source_chapter ? (
        <p className="source-line">
          Source: Chapter {record.source_chapter.chapter_number}, {record.source_chapter.title}
        </p>
      ) : null}

      {record.review_warnings && record.review_warnings.length > 0 ? (
        <div className="review-warning-list">
          <strong>Review warnings</strong>
          {record.review_warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      {entityType === "characters" ? (
        <div className="meta-lines">
          <span>
            First mentioned:{" "}
            {record.first_mentioned_chapter
              ? `Chapter ${record.first_mentioned_chapter.chapter_number}`
              : "Unknown"}
          </span>
          <span>
            First appeared:{" "}
            {record.first_appeared_chapter
              ? `Chapter ${record.first_appeared_chapter.chapter_number}`
              : "Unknown"}
          </span>
          {record.current_cultivation_level ? (
            <span>Current cultivation: {record.current_cultivation_level}</span>
          ) : null}
          {record.current_position ? <span>Current position: {record.current_position}</span> : null}
          {record.current_class_rank ? (
            <span>Current class rank: {record.current_class_rank}</span>
          ) : null}
          {record.current_power_rank ? <span>Current power rank: {record.current_power_rank}</span> : null}
        </div>
      ) : null}

      {(entityType === "characters" || entityType === "skills") &&
      record.aliases &&
      record.aliases.length > 0 ? (
        <div className="alias-list">
          <strong>Aliases</strong>
          {record.aliases.map((alias) => (
            <span key={alias.id}>{alias.alias}</span>
          ))}
        </div>
      ) : null}

      {fields.map((field) => (
        <label key={field}>
          {field.replace("_", " ")}
          {field === "description" ? (
            <textarea
              value={formValues[field]}
              onChange={(event) => setFormValues({ ...formValues, [field]: event.target.value })}
            />
          ) : (
            <input
              type="text"
              value={formValues[field]}
              onChange={(event) => setFormValues({ ...formValues, [field]: event.target.value })}
            />
          )}
        </label>
      ))}

      <label>
        admin notes
        <textarea
          value={formValues.admin_notes}
          onChange={(event) => setFormValues({ ...formValues, admin_notes: event.target.value })}
          placeholder="Optional review notes"
        />
      </label>

      {record.evidence && record.evidence.length > 0 ? (
        <div className="evidence-list">
          <strong>Evidence</strong>
          {record.evidence.map((evidence) => (
            <p key={evidence.id}>{evidence.evidence_text}</p>
          ))}
        </div>
      ) : null}

      <div className="review-actions">
        <button type="button" disabled={isSaving} onClick={() => saveRecord()}>
          Save
        </button>
        <button type="button" disabled={isSaving} onClick={() => saveRecord({ review_status: "approved" })}>
          Approve
        </button>
        <button type="button" disabled={isSaving} onClick={() => saveRecord({ review_status: "rejected" })}>
          Reject
        </button>
      </div>

      {entityType === "characters" && mergeTargets.length > 0 ? (
        <div className="merge-row">
          <select
            value={mergeTargetId}
            onChange={(event) => setMergeTargetId(event.target.value)}
            disabled={isSaving}
          >
            <option value="">Merge into...</option>
            {mergeTargets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.name}
              </option>
            ))}
          </select>
          <button type="button" disabled={isSaving || !mergeTargetId} onClick={mergeCharacter}>
            Merge
          </button>
        </div>
      ) : null}
    </article>
  );
}
