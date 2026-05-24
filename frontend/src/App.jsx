import React from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "./api.js";
import ReviewRecord from "./components/admin/ReviewRecord.jsx";
import WikiPanel from "./components/wiki/WikiPanel.jsx";
import WikiNovelRoute from "./components/wiki/WikiNovelRoute.jsx";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeView = location.pathname.startsWith("/admin") ? "admin" : "wiki";
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
  const [hideApprovedReviewCards, setHideApprovedReviewCards] = React.useState(false);
  const [hideRejectedReviewCards, setHideRejectedReviewCards] = React.useState(true);
  const [wikiCharacters, setWikiCharacters] = React.useState([]);
  const [wikiItems, setWikiItems] = React.useState([]);
  const [wikiLoading, setWikiLoading] = React.useState(false);
  const [wikiNovel, setWikiNovel] = React.useState(null);
  const [wikiNovels, setWikiNovels] = React.useState([]);
  const [wikiProgressionEvents, setWikiProgressionEvents] = React.useState([]);
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
      const [novelData, charactersData, skillsData, itemsData, progressionData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/characters`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/skills`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/items`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/progression`),
      ]);

      setWikiNovel(novelData);
      setWikiCharacters(charactersData);
      setWikiSkills(skillsData);
      setWikiItems(itemsData);
      setWikiProgressionEvents(progressionData);
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
        [entityType]: (currentData[entityType] || []).map((record) =>
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
    const metadataProposalCount = summary.metadata_proposals_created || 0;

    return (
      `Chapter ${chapter.chapter_number} extracted: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${metadataProposalCount} metadata proposals, ` +
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
    const metadataProposalCount = summary.metadata_proposals_created || 0;

    return (
      `Extracted ${data.extracted_chapter_count} chapters: ` +
      `${characterCount} characters, ${skillCount} skills, ` +
      `${itemCount} items, ${characterSkillCount} character skills, ` +
      `${summary.progression_events_created} progression, ` +
      `${metadataProposalCount} metadata proposals, ` +
      `${summary.life_events_created} life events.`
    );
  }

  function reviewEntityConfigs() {
    return [
      {
        key: "characters",
        label: "Character",
        fields: ["name", "description"],
        records: extractedData?.characters || [],
      },
      {
        key: "character_metadata_proposals",
        label: "Metadata Update",
        fields: ["proposed_value"],
        records: extractedData?.character_metadata_proposals || [],
      },
      {
        key: "progression_events",
        label: "Progression",
        fields: ["progression_type", "old_value", "new_value", "description"],
        records: extractedData?.progression_events || [],
      },
      {
        key: "character_skills",
        label: "Character Skill",
        fields: ["relationship_type", "description"],
        records: extractedData?.character_skills || [],
      },
      {
        key: "skills",
        label: "Skill",
        fields: ["name", "category", "description"],
        records: extractedData?.skills || [],
      },
      {
        key: "items",
        label: "Item",
        fields: ["name", "category", "description"],
        records: extractedData?.items || [],
      },
      {
        key: "character_items",
        label: "Character Item",
        fields: ["relationship_type", "description"],
        records: extractedData?.character_items || [],
      },
      {
        key: "life_events",
        label: "Life Event",
        fields: ["event_type", "description", "reason"],
        records: extractedData?.life_events || [],
      },
      {
        key: "events",
        label: "Timeline Fact",
        fields: ["event_type", "title", "description"],
        records: extractedData?.events || [],
      },
    ];
  }

  function chapterNumberForRecord(record) {
    return record.source_chapter?.chapter_number || record.chapter?.chapter_number || 999999;
  }

  function chapterTitleForRecord(record) {
    const chapter = record.source_chapter || record.chapter;
    return chapter ? `Chapter ${chapter.chapter_number}: ${chapter.title}` : "Unknown chapter";
  }

  function reviewRecords() {
    return reviewEntityConfigs()
      .flatMap((config, entityIndex) =>
        config.records.map((record, recordIndex) => ({
          config,
          entityIndex,
          record,
          recordIndex,
        }))
      )
      .filter((item) => !hideRejectedReviewCards || item.record.review_status !== "rejected")
      .filter((item) => !hideApprovedReviewCards || item.record.review_status !== "approved")
      .sort((first, second) => {
        const chapterDifference =
          chapterNumberForRecord(first.record) - chapterNumberForRecord(second.record);

        if (chapterDifference !== 0) {
          return chapterDifference;
        }

        if (first.entityIndex !== second.entityIndex) {
          return first.entityIndex - second.entityIndex;
        }

        return first.record.id - second.record.id;
      });
  }

  function groupedReviewRecords() {
    const groups = [];

    for (const item of reviewRecords()) {
      const chapterTitle = chapterTitleForRecord(item.record);
      let group = groups.find((candidate) => candidate.title === chapterTitle);

      if (!group) {
        group = { title: chapterTitle, items: [] };
        groups.push(group);
      }

      group.items.push(item);
    }

    return groups;
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
    <main className={activeView === "wiki" ? "app-shell wiki-shell" : "app-shell"}>
      <section className="page-header">
        <p className="eyebrow">{activeView === "admin" ? "Admin MVP" : "Public Wiki"}</p>
        <h1>{activeView === "admin" ? "NovelWiki Upload Verification" : "NovelWiki"}</h1>
        <div className="view-toggle">
          <button
            className={activeView === "admin" ? "active" : ""}
            type="button"
            onClick={() => navigate("/admin")}
          >
            Admin
          </button>
          <button
            className={activeView === "wiki" ? "active" : ""}
            type="button"
            onClick={() => {
              navigate("/wiki/novels");
              loadWikiNovels().catch((error) => setMessage(error.message));
            }}
          >
            Wiki
          </button>
        </div>
      </section>

      {message ? <p className="message">{message}</p> : null}

      {activeView === "wiki" ? (
        <Routes>
          <Route path="/" element={<Navigate to="/wiki/novels" replace />} />
          <Route path="/wiki" element={<Navigate to="/wiki/novels" replace />} />
          <Route
            path="/wiki/novels"
            element={
              <WikiPanel
                characters={[]}
                items={[]}
                loading={wikiLoading}
                novel={null}
                novels={wikiNovels}
                onLoadNovel={loadWikiNovel}
                onOpenAdmin={() => navigate("/admin")}
                onSelectCharacter={loadWikiCharacter}
                page="Novels"
                progressionEvents={[]}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={null}
                selectedSkill={null}
                skills={[]}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Overview"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/characters"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Characters"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/characters/:characterId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Characters"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={wikiSelectedCharacter}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/characters/:characterId/progression"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="CharacterProgression"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={wikiSelectedCharacter}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/cultivation"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Cultivation"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/skills"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Skills"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/skills/:skillId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Skills"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={wikiSelectedSkill}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/items"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Items"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={null}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
          <Route
            path="/wiki/novels/:novelId/items/:itemId"
            element={
              <WikiNovelRoute
                characters={wikiCharacters}
                items={wikiItems}
                loadCharacter={loadWikiCharacter}
                loadItem={loadWikiItem}
                loadSkill={loadWikiSkill}
                loading={wikiLoading}
                loadNovel={loadWikiNovel}
                novel={wikiNovel}
                novels={wikiNovels}
                onOpenAdmin={() => navigate("/admin")}
                page="Items"
                progressionEvents={wikiProgressionEvents}
                selectedCharacter={null}
                selectedItem={wikiSelectedItem}
                selectedNovelId={wikiSelectedNovelId}
                selectedSkill={null}
                setMessage={setMessage}
                skills={wikiSkills}
              />
            }
          />
        </Routes>
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
                  <div className="review-stream">
                    <div className="review-stream-toolbar">
                      <strong>Chapter-sorted review list</strong>
                      <div className="review-filter-row">
                        <label className="review-checkbox">
                          <input
                            type="checkbox"
                            checked={hideApprovedReviewCards}
                            onChange={(event) => setHideApprovedReviewCards(event.target.checked)}
                          />
                          Hide approved
                        </label>
                        <label className="review-checkbox">
                          <input
                            type="checkbox"
                            checked={hideRejectedReviewCards}
                            onChange={(event) => setHideRejectedReviewCards(event.target.checked)}
                          />
                          Hide rejected
                        </label>
                      </div>
                    </div>

                    {groupedReviewRecords().map((group) => (
                      <section className="review-chapter-group" key={group.title}>
                        <h3>{group.title}</h3>
                        {group.items.map(({ config, record }) => (
                          <div className="review-stream-item" key={`${config.key}-${record.id}`}>
                            <span className="review-type-pill">{config.label}</span>
                            <ReviewRecord
                              entityType={config.key}
                              fields={config.fields}
                              mergeTargets={
                                config.key === "characters"
                                  ? extractedData.characters.filter((target) => target.id !== record.id)
                                  : []
                              }
                              record={record}
                              onMerged={handleMergedCharacter}
                              onSaved={(updatedRecord) => updateExtractedRecord(config.key, updatedRecord)}
                            />
                          </div>
                        ))}
                      </section>
                    ))}

                    {reviewRecords().length === 0 ? (
                      <p className="empty-state">
                        {hideApprovedReviewCards || hideRejectedReviewCards
                          ? "No visible review records. Some statuses may be hidden."
                          : "No extracted records yet."}
                      </p>
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
