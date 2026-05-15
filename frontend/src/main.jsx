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

      {record.skill_name ? <p className="source-line">Skill: {record.skill_name}</p> : null}
      {record.item_name ? <p className="source-line">Item: {record.item_name}</p> : null}

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

function WikiRecordList({ emptyText, items, onSelect, selectedId }) {
  if (items.length === 0) {
    return <p className="empty-state">{emptyText}</p>;
  }

  return (
    <div className="wiki-list">
      {items.map((item) => (
        <button
          className={selectedId === item.id ? "wiki-list-button active" : "wiki-list-button"}
          key={item.id}
          type="button"
          onClick={() => onSelect(item)}
        >
          <strong>{item.name}</strong>
          {item.current_cultivation_level ? <small>{item.current_cultivation_level}</small> : null}
          {item.current_position ? <small>{item.current_position}</small> : null}
          {item.category ? <small>{item.category}</small> : null}
        </button>
      ))}
    </div>
  );
}

function WikiEvidence({ evidence }) {
  if (!evidence || evidence.length === 0) {
    return null;
  }

  return (
    <div className="evidence-list">
      <strong>Evidence</strong>
      {evidence.map((row) => (
        <p key={row.id}>
          {row.chapter ? `Chapter ${row.chapter.chapter_number}: ` : ""}
          {row.evidence_text}
        </p>
      ))}
    </div>
  );
}

function firstDescriptionChunk(description) {
  if (!description) {
    return "";
  }

  return description.split(/\n\s*\n/)[0].trim();
}

function WikiCharacterDetail({ character }) {
  if (!character) {
    return <p>Select a character to read their wiki page.</p>;
  }

  const displayDescription = firstDescriptionChunk(character.description);

  return (
    <article className="wiki-detail">
      <h3>{character.name}</h3>

      <div className="meta-lines">
        {character.current_cultivation_level ? (
          <span>Current cultivation: {character.current_cultivation_level}</span>
        ) : null}
        {character.current_position ? <span>Current position: {character.current_position}</span> : null}
        {character.first_mentioned_chapter ? (
          <span>First mentioned: Chapter {character.first_mentioned_chapter.chapter_number}</span>
        ) : null}
        {character.first_appeared_chapter ? (
          <span>First appeared: Chapter {character.first_appeared_chapter.chapter_number}</span>
        ) : null}
      </div>

      {character.aliases && character.aliases.length > 0 ? (
        <div className="alias-list">
          <strong>Aliases</strong>
          {character.aliases.map((alias) => (
            <span key={alias.id}>{alias.alias}</span>
          ))}
        </div>
      ) : null}

      {displayDescription ? <p>{displayDescription}</p> : null}

      <section className="wiki-subsection">
        <h4>Progression</h4>
        {character.progression_events && character.progression_events.length === 0 ? (
          <p>No approved progression yet.</p>
        ) : null}
        {(character.progression_events || []).map((event) => (
          <article className="mini-record" key={event.id}>
            <strong>{event.new_value}</strong>
            <p>
              {event.chapter ? `Chapter ${event.chapter.chapter_number}` : "Unknown chapter"}
              {event.old_value ? `, from ${event.old_value}` : ""}
            </p>
            {event.description ? <p>{event.description}</p> : null}
            <WikiEvidence evidence={event.evidence} />
          </article>
        ))}
      </section>

      {character.skills && character.skills.length > 0 ? (
        <section className="wiki-subsection">
          <h4>Skills</h4>
          {character.skills.map((relationship) => (
            <article className="mini-record" key={relationship.id}>
              <strong>{relationship.skill ? relationship.skill.name : "Unknown skill"}</strong>
              <p>
                {relationship.relationship_type.replace("_", " ")}
                {relationship.chapter ? `, Chapter ${relationship.chapter.chapter_number}` : ""}
              </p>
              {relationship.description ? <p>{relationship.description}</p> : null}
              <WikiEvidence evidence={relationship.evidence} />
            </article>
          ))}
        </section>
      ) : null}

      {character.items && character.items.length > 0 ? (
        <section className="wiki-subsection">
          <h4>Items</h4>
          {character.items.map((relationship) => (
            <article className="mini-record" key={relationship.id}>
              <strong>{relationship.item ? relationship.item.name : "Unknown item"}</strong>
              <p>
                {relationship.relationship_type.replace("_", " ")}
                {relationship.chapter ? `, Chapter ${relationship.chapter.chapter_number}` : ""}
              </p>
              {relationship.description ? <p>{relationship.description}</p> : null}
              <WikiEvidence evidence={relationship.evidence} />
            </article>
          ))}
        </section>
      ) : null}

      {character.life_events && character.life_events.length > 0 ? (
        <section className="wiki-subsection">
          <h4>Life Events</h4>
          {character.life_events.map((event) => (
            <article className="mini-record" key={event.id}>
              <strong>{event.event_type.replace("_", " ")}</strong>
              {event.description ? <p>{event.description}</p> : null}
              {event.reason ? <p>Reason: {event.reason}</p> : null}
              <WikiEvidence evidence={event.evidence} />
            </article>
          ))}
        </section>
      ) : null}
    </article>
  );
}

function WikiSkillDetail({ skill }) {
  if (!skill) {
    return <p>Select a skill to read its wiki page.</p>;
  }

  return (
    <article className="wiki-detail">
      <h3>{skill.name}</h3>

      {skill.category ? (
        <div className="meta-lines">
          <span>Category: {skill.category}</span>
        </div>
      ) : null}

      {skill.aliases && skill.aliases.length > 0 ? (
        <div className="alias-list">
          <strong>Aliases</strong>
          {skill.aliases.map((alias) => (
            <span key={alias.id}>{alias.alias}</span>
          ))}
        </div>
      ) : null}

      {skill.description ? <p>{skill.description}</p> : null}

      <WikiEvidence evidence={skill.evidence} />
    </article>
  );
}

function WikiItemDetail({ item }) {
  if (!item) {
    return <p>Select an item to read its wiki page.</p>;
  }

  return (
    <article className="wiki-detail">
      <h3>{item.name}</h3>

      {item.category ? (
        <div className="meta-lines">
          <span>Category: {item.category}</span>
        </div>
      ) : null}

      {item.description ? <p>{item.description}</p> : null}

      <WikiEvidence evidence={item.evidence} />
    </article>
  );
}

function WikiPanel({
  characters,
  items,
  loading,
  novel,
  novels,
  onLoadNovel,
  onSelectCharacter,
  onSelectItem,
  onSelectSkill,
  selectedCharacter,
  selectedItem,
  selectedNovelId,
  selectedSkill,
  skills,
}) {
  return (
    <section className="layout wiki-layout">
      <aside className="panel novel-list">
        <h2>Wiki Novels</h2>
        {novels.length === 0 ? <p>No novels available.</p> : null}
        {novels.map((wikiNovel) => (
          <button
            className={selectedNovelId === wikiNovel.id ? "novel-button active" : "novel-button"}
            key={wikiNovel.id}
            type="button"
            onClick={() => onLoadNovel(wikiNovel.id)}
          >
            <span>{wikiNovel.title}</span>
            <small>{wikiNovel.chapter_count} chapters</small>
            <small>{wikiNovel.approved_character_count} approved characters</small>
          </button>
        ))}
      </aside>

      <div className="content-stack">
        <section className="panel">
          <h2>{novel ? novel.title : "Public Wiki"}</h2>
          {!novel ? <p>Select a novel to view approved wiki data.</p> : null}
          {loading ? <p>Loading wiki data...</p> : null}
          {novel ? (
            <div className="summary-row">
              <span>{novel.approved_character_count} characters</span>
              <span>{novel.approved_skill_count} skills</span>
              <span>{novel.approved_item_count} items</span>
            </div>
          ) : null}
        </section>

        {novel ? (
          <section className="wiki-grid">
            <div className="panel">
              <h2>Characters</h2>
              <WikiRecordList
                emptyText="No approved characters yet."
                items={characters}
                onSelect={onSelectCharacter}
                selectedId={selectedCharacter ? selectedCharacter.id : null}
              />
            </div>

            <div className="panel">
              <h2>Character Page</h2>
              <WikiCharacterDetail character={selectedCharacter} />
            </div>

            <div className="panel">
              <h2>Skills</h2>
              <WikiRecordList
                emptyText="No approved skills yet."
                items={skills}
                onSelect={onSelectSkill}
                selectedId={selectedSkill ? selectedSkill.id : null}
              />
            </div>

            <div className="panel">
              <h2>Skill Page</h2>
              <WikiSkillDetail skill={selectedSkill} />
            </div>

            <div className="panel">
              <h2>Items</h2>
              <WikiRecordList
                emptyText="No approved items yet."
                items={items}
                onSelect={onSelectItem}
                selectedId={selectedItem ? selectedItem.id : null}
              />
            </div>

            <div className="panel">
              <h2>Item Page</h2>
              <WikiItemDetail item={selectedItem} />
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}

function App() {
  const [activeView, setActiveView] = React.useState("admin");
  const [novels, setNovels] = React.useState([]);
  const [selectedNovelId, setSelectedNovelId] = React.useState(null);
  const [chapterResult, setChapterResult] = React.useState(null);
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [message, setMessage] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [isBatchExtracting, setIsBatchExtracting] = React.useState(false);
  const [extractingChapterId, setExtractingChapterId] = React.useState(null);
  const [extractedData, setExtractedData] = React.useState(null);
  const [wikiCharacters, setWikiCharacters] = React.useState([]);
  const [wikiItems, setWikiItems] = React.useState([]);
  const [wikiLoading, setWikiLoading] = React.useState(false);
  const [wikiNovel, setWikiNovel] = React.useState(null);
  const [wikiNovels, setWikiNovels] = React.useState([]);
  const [wikiSelectedCharacter, setWikiSelectedCharacter] = React.useState(null);
  const [wikiSelectedItem, setWikiSelectedItem] = React.useState(null);
  const [wikiSelectedNovelId, setWikiSelectedNovelId] = React.useState(null);
  const [wikiSelectedSkill, setWikiSelectedSkill] = React.useState(null);
  const [wikiSkills, setWikiSkills] = React.useState([]);

  async function loadNovels() {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels`);
    setNovels(data);
  }

  async function loadWikiNovels() {
    const data = await fetchJson(`${API_BASE_URL}/wiki/novels`);
    setWikiNovels(data);
  }

  async function loadWikiNovel(novelId) {
    setWikiLoading(true);
    setWikiSelectedNovelId(novelId);
    setWikiSelectedCharacter(null);
    setWikiSelectedSkill(null);
    setWikiSelectedItem(null);

    try {
      const [novelData, charactersData, skillsData, itemsData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/characters`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/skills`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/items`),
      ]);

      setWikiNovel(novelData);
      setWikiCharacters(charactersData);
      setWikiSkills(skillsData);
      setWikiItems(itemsData);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiCharacter(character) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/characters/${character.id}`);
      setWikiSelectedCharacter(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiSkill(skill) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/skills/${skill.id}`);
      setWikiSelectedSkill(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiItem(item) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/items/${item.id}`);
      setWikiSelectedItem(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
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

  async function handleExtractFirstFifteen() {
    if (!selectedNovelId) {
      setMessage("Select a novel first.");
      return;
    }

    setIsBatchExtracting(true);
    setMessage("Extracting first 15 chapters in order...");

    try {
      const data = await fetchJson(
        `${API_BASE_URL}/admin/novels/${selectedNovelId}/extract-first-15`,
        {
          method: "POST",
        }
      );

      setExtractedData(data);
      setMessage(buildBatchExtractionMessage(data));
      await loadNovels();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsBatchExtracting(false);
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
    const characterSkillCount = summary.character_skills_created || 0;

    return (
      `Chapter ${chapter.chapter_number} extracted: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${summary.life_events_created} life events, ${summary.events_created} timeline facts.`
    );
  }

  function buildBatchExtractionMessage(data) {
    if (!data.summary || !data.extracted_chapter_count) {
      return "Batch extraction finished. Review the pending records below.";
    }

    const summary = data.summary;
    const characterCount = summary.characters_created + summary.characters_updated;
    const skillCount = summary.skills_created + summary.skills_updated;
    const itemCount = summary.items_created + summary.items_updated;
    const characterSkillCount = summary.character_skills_created || 0;

    return (
      `Extracted ${data.extracted_chapter_count} chapters: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${summary.life_events_created} life events.`
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
    loadWikiNovels().catch((error) => setMessage(error.message));
  }, []);

  return (
    <main className="app-shell">
      <section className="page-header">
        <p className="eyebrow">{activeView === "admin" ? "Admin MVP" : "Public Wiki"}</p>
        <h1>{activeView === "admin" ? "NovelWiki Upload Verification" : "NovelWiki"}</h1>
        <div className="view-toggle">
          <button
            className={activeView === "admin" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("admin")}
          >
            Admin
          </button>
          <button
            className={activeView === "wiki" ? "active" : ""}
            type="button"
            onClick={() => {
              setActiveView("wiki");
              loadWikiNovels().catch((error) => setMessage(error.message));
            }}
          >
            Wiki
          </button>
        </div>
      </section>

      {message ? <p className="message">{message}</p> : null}

      {activeView === "wiki" ? (
        <WikiPanel
          characters={wikiCharacters}
          items={wikiItems}
          loading={wikiLoading}
          novel={wikiNovel}
          novels={wikiNovels}
          onLoadNovel={loadWikiNovel}
          onSelectCharacter={loadWikiCharacter}
          onSelectItem={loadWikiItem}
          onSelectSkill={loadWikiSkill}
          selectedCharacter={wikiSelectedCharacter}
          selectedItem={wikiSelectedItem}
          selectedNovelId={wikiSelectedNovelId}
          selectedSkill={wikiSelectedSkill}
          skills={wikiSkills}
        />
      ) : (
        <>
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
                              disabled={isBatchExtracting || extractingChapterId === chapter.id}
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
                  <div className="button-row">
                    <button
                      type="button"
                      disabled={!selectedNovelId || isProcessing || isBatchExtracting}
                      onClick={handleProcessNovel}
                    >
                      {isProcessing ? "Processing..." : "Run Placeholder Processing"}
                    </button>
                    <button
                      type="button"
                      disabled={!selectedNovelId || isBatchExtracting || extractingChapterId}
                      onClick={handleExtractFirstFifteen}
                    >
                      {isBatchExtracting ? "Extracting 1-15..." : "Extract First 15"}
                    </button>
                  </div>
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
                      <h3>Character Skills</h3>
                      {extractedData.character_skills.map((relationship) => (
                        <ReviewRecord
                          entityType="character_skills"
                          fields={["relationship_type", "description"]}
                          key={relationship.id}
                          record={relationship}
                          onSaved={(updatedRecord) =>
                            updateExtractedRecord("character_skills", updatedRecord)
                          }
                        />
                      ))}
                    </section>

                    <section>
                      <h3>Character Items</h3>
                      {extractedData.character_items.map((relationship) => (
                        <ReviewRecord
                          entityType="character_items"
                          fields={["relationship_type", "description"]}
                          key={relationship.id}
                          record={relationship}
                          onSaved={(updatedRecord) =>
                            updateExtractedRecord("character_items", updatedRecord)
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
                    extractedData.character_skills.length === 0 &&
                    extractedData.character_items.length === 0 &&
                    extractedData.life_events.length === 0 ? (
                      <p className="empty-state">No extracted records yet.</p>
                    ) : null}
                  </div>
                ) : null}
              </section>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
