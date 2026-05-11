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

function App() {
  const [novels, setNovels] = React.useState([]);
  const [selectedNovelId, setSelectedNovelId] = React.useState(null);
  const [chapterResult, setChapterResult] = React.useState(null);
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [message, setMessage] = React.useState("");
  const [isUploading, setIsUploading] = React.useState(false);

  async function loadNovels() {
    const data = await fetchJson(`${API_BASE_URL}/admin/novels`);
    setNovels(data);
  }

  async function loadChapters(novelId) {
    setSelectedNovelId(novelId);
    const data = await fetchJson(`${API_BASE_URL}/admin/novels/${novelId}/chapters`);
    setChapterResult(data);
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
            </button>
          ))}
        </aside>

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
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
