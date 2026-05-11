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

function ReviewRecord({ entityType, record, fields, onSaved }) {
  const [formValues, setFormValues] = React.useState(() => {
    const values = {};

    fields.forEach((field) => {
      values[field] = record[field] || "";
    });

    values.admin_notes = record.admin_notes || "";
    return values;
  });
  const [isSaving, setIsSaving] = React.useState(false);

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

  return (
    <article className="mini-record review-record">
      <div className="record-title-row">
        <strong>{record.name || record.title || record.entity_type}</strong>
        <span className={`status-pill ${record.review_status}`}>{record.review_status}</span>
      </div>

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
                      <span>{chapter.character_count.toLocaleString()} chars</span>
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
                      record={character}
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
                  <h3>Events</h3>
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

                <section className="wide-record">
                  <h3>Evidence</h3>
                  {extractedData.evidence.map((evidence) => (
                    <article className="mini-record" key={evidence.id}>
                      <strong>{evidence.entity_type}</strong>
                      <p>{evidence.evidence_text}</p>
                    </article>
                  ))}
                </section>

                {extractedData.characters.length === 0 &&
                extractedData.skills.length === 0 &&
                extractedData.items.length === 0 &&
                extractedData.events.length === 0 ? (
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
