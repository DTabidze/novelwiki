import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_BASE_URL = "http://127.0.0.1:5050/api";

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }

  return body.data;
}

function ReviewRecord({ entityType, record, fields, mergeTargets = [], onMerged, onSaved }) {
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

      {record.source_chapter ? (
        <p className="source-line">
          Source: Chapter {record.source_chapter.chapter_number}, {record.source_chapter.title}
        </p>
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

function App() {
  const [novels, setNovels] = React.useState([]);
  const [selectedNovelId, setSelectedNovelId] = React.useState(null);
  const [chapterResult, setChapterResult] = React.useState(null);
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [message, setMessage] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [extractingChapterId, setExtractingChapterId] = React.useState(null);
  const [extractedData, setExtractedData] = React.useState(null);

  async function loadNovels() {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels`);
    setNovels(data);
  }

  async function loadChapters(novelId) {
    setSelectedNovelId(novelId);
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters`);
    setChapterResult(data);
    await loadExtractedData(novelId);
  }

  async function loadExtractedData(novelId) {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/extracted-data`);
    setExtractedData(data);
  }

  async function handleProcessNovel() {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setIsProcessing(true);
    setMessage("");

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/${selectedNovelId}/process`, {
        method: "POST",
      });

      setExtractedData(data);
      setMessage(`Processed ${data.novel.title} with placeholder extraction.`);
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleExtractChapter(chapterId) {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setExtractingChapterId(chapterId);
    setMessage("");

    try {
      const data = await fetchJson(
        `${API_BASE_URL}/admin/novels/${selectedNovelId}/chapters/${chapterId}/extract`,
        {
          method: "POST",
        }
      );

      setExtractedData(data);
      setMessage(buildExtractionMessage(data));
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setExtractingChapterId(null);
    }
  }

  function updateExtractedRecord(entityType, updatedRecord) {
    setExtractedData((currentData) => {
      if (!currentData) {
        return currentData;
      }

      return {
        ...currentData,
        [entityType]: currentData[entityType].map((record) =>
          record.id === updatedRecord.id ? updatedRecord : record
        ),
      };
    });
    setMessage("Review saved.");
  }

  async function handleMergedCharacter() {
    if (selectedNovelId) {
      await loadExtractedData(selectedNovelId);
    }

    setMessage("Characters merged.");
  }

  function buildExtractionMessage(data) {
    if (!data.summary || !data.extracted_chapter) {
      return "AI extraction finished for one chapter. Review the pending records below.";
    }

    const summary = data.summary;
    const chapter = data.extracted_chapter;
    const characterCount = summary.characters_created + summary.characters_updated;
    const skillCount = summary.skills_created + summary.skills_updated;
    const itemCount = summary.items_created + summary.items_updated;

    return (
      `Chapter ${chapter.chapter_number} extracted: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${summary.progression_events_created} progression, ` +
      `${summary.life_events_created} life events, ${summary.events_created} timeline facts.`
    );
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!file) {
      setMessage("Choose a .txt file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);

    setIsUploading(true);
    setMessage("");

    try {
      const data = await fetchJson(`${API_BASE_URL}/admin/novels/upload`, {
        method: "POST",
        body: formData,
      });

      setMessage(`Uploaded ${data.novel.title} with ${data.chapter_count} chapters.`);
      setTitle("");
      setFile(null);
      event.target.reset();
      await loadNovels();
      await loadChapters(data.novel.id);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsUploading(false);
    }
  }

  React.useEffect(() => {
    loadNovels().catch((error) => setMessage(error.message));
  }, []);

  return (
    <main className="app-shell">
      <section className="page-header">
        <p className="eyebrow">Admin MVP</p>
        <h1>NovelWiki Upload Verification</h1>
      </section>

      <section className="panel">
        <h2>Upload .txt Novel</h2>
        <form className="upload-form" onSubmit={handleUpload}>
          <label>
            Novel title
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional, defaults to file name"
            />
          </label>

          <label>
            Novel file
            <input
              type="file"
              accept=".txt,text/plain"
              onChange={(event) => setFile(event.target.files[0])}
            />
          </label>

          <button type="submit" disabled={isUploading}>
            {isUploading ? "Uploading..." : "Upload and Split"}
          </button>
        </form>
        {message ? <p className="message">{message}</p> : null}
      </section>

      <section className="layout">
        <aside className="panel novel-list">
          <h2>Uploaded Novels</h2>
          {novels.length === 0 ? <p>No novels uploaded yet.</p> : null}
          {novels.map((novel) => (
            <button
              className={selectedNovelId === novel.id ? "novel-button active" : "novel-button"}
              key={novel.id}
              type="button"
              onClick={() => loadChapters(novel.id).catch((error) => setMessage(error.message))}
            >
              <span>{novel.title}</span>
              <small>{novel.chapter_count} chapters</small>
              <small>Status: {novel.status}</small>
            </button>
          ))}
        </aside>

        <div className="content-stack">
          <section className="panel chapter-panel">
            <h2>Chapter Verification</h2>
            {!chapterResult ? <p>Select a novel to inspect chapter metadata.</p> : null}
            {chapterResult ? (
              <>
                <div className="summary-row">
                  <strong>{chapterResult.novel.title}</strong>
                  <span>{chapterResult.chapters.length} chapters</span>
                </div>
                <div className="chapter-table">
                  {chapterResult.chapters.map((chapter) => (
                    <article className="chapter-row" key={chapter.id}>
                      <div>
                        <strong>
                          {chapter.chapter_number}. {chapter.title}
                        </strong>
                        <p>{chapter.preview}</p>
                      </div>
                      <div className="chapter-actions">
                        <span>{chapter.character_count.toLocaleString()} chars</span>
                        <button
                          type="button"
                          disabled={extractingChapterId === chapter.id}
                          onClick={() => handleExtractChapter(chapter.id)}
                        >
                          {extractingChapterId === chapter.id ? "Extracting..." : "AI Extract"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            ) : null}
          </section>

          <section className="panel extraction-panel">
            <div className="panel-header">
              <h2>Extraction Pipeline</h2>
              <button type="button" disabled={!selectedNovelId || isProcessing} onClick={handleProcessNovel}>
                {isProcessing ? "Processing..." : "Run Placeholder Processing"}
              </button>
            </div>

            {!selectedNovelId ? <p>Select a novel to run placeholder extraction.</p> : null}
            {selectedNovelId && !extractedData ? <p>No extracted data loaded yet.</p> : null}

            {extractedData ? (
              <div className="extraction-grid">
                <section>
                  <h3>Characters</h3>
                  {extractedData.characters.map((character) => (
                    <ReviewRecord
                      entityType="characters"
                      fields={["name", "description"]}
                      key={character.id}
                      mergeTargets={extractedData.characters.filter((target) => target.id !== character.id)}
                      record={character}
                      onMerged={handleMergedCharacter}
                      onSaved={(updatedRecord) => updateExtractedRecord("characters", updatedRecord)}
                    />
                  ))}
                </section>

                <section>
                  <h3>Skills</h3>
                  {extractedData.skills.map((skill) => (
                    <ReviewRecord
                      entityType="skills"
                      fields={["name", "category", "description"]}
                      key={skill.id}
                      record={skill}
                      onSaved={(updatedRecord) => updateExtractedRecord("skills", updatedRecord)}
                    />
                  ))}
                </section>

                <section>
                  <h3>Items</h3>
                  {extractedData.items.map((item) => (
                    <ReviewRecord
                      entityType="items"
                      fields={["name", "category", "description"]}
                      key={item.id}
                      record={item}
                      onSaved={(updatedRecord) => updateExtractedRecord("items", updatedRecord)}
                    />
                  ))}
                </section>

                <section>
                  <h3>Timeline Facts</h3>
                  {extractedData.events.map((event) => (
                    <ReviewRecord
                      entityType="events"
                      fields={["event_type", "title", "description"]}
                      key={event.id}
                      record={event}
                      onSaved={(updatedRecord) => updateExtractedRecord("events", updatedRecord)}
                    />
                  ))}
                </section>

                <section>
                  <h3>Progression</h3>
                  {extractedData.progression_events.map((event) => (
                    <ReviewRecord
                      entityType="progression_events"
                      fields={["progression_type", "old_value", "new_value", "description"]}
                      key={event.id}
                      record={event}
                      onSaved={(updatedRecord) =>
                        updateExtractedRecord("progression_events", updatedRecord)
                      }
                    />
                  ))}
                </section>

                <section>
                  <h3>Life Events</h3>
                  {extractedData.life_events.map((event) => (
                    <ReviewRecord
                      entityType="life_events"
                      fields={["event_type", "description", "reason"]}
                      key={event.id}
                      record={event}
                      onSaved={(updatedRecord) => updateExtractedRecord("life_events", updatedRecord)}
                    />
                  ))}
                </section>

                {extractedData.characters.length === 0 &&
                extractedData.skills.length === 0 &&
                extractedData.items.length === 0 &&
                extractedData.events.length === 0 &&
                extractedData.progression_events.length === 0 &&
                extractedData.life_events.length === 0 ? (
                  <p className="empty-state">No extracted records yet.</p>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
