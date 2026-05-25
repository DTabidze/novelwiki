import React from "react";
import ChapterPreviewPanel from "./ChapterPreviewPanel.jsx";

function chapterMatchesStatus(chapter, status) {
  if (status === "all") {
    return true;
  }

  if (status === "pending") {
    return (chapter.pending_review_count || 0) > 0;
  }

  if (status === "warnings") {
    return (chapter.warning_count || 0) > 0;
  }

  return true;
}

function bookOptionLabel(book) {
  const defaultTitle = `Book ${book.number}`;

  if (!book.title || book.title === defaultTitle) {
    return defaultTitle;
  }

  return `${defaultTitle} - ${book.title}`;
}

export default function ChaptersPage({
  books,
  chapters,
  extractingChapterId,
  initialBookId,
  onExtractChapter,
  onOpenReview,
}) {
  const [activeBookId, setActiveBookId] = React.useState(initialBookId || "all");
  const [chapterEnd, setChapterEnd] = React.useState("");
  const [chapterStart, setChapterStart] = React.useState("");
  const [searchTerm, setSearchTerm] = React.useState("");
  const [selectedChapterId, setSelectedChapterId] = React.useState(null);
  const [statusFilter, setStatusFilter] = React.useState("all");

  React.useEffect(() => {
    if (initialBookId) {
      setActiveBookId(initialBookId);
    }
  }, [initialBookId]);

  const filteredChapters = chapters.filter((chapter) => {
    const matchesBook = activeBookId === "all" || chapter.book_id === Number(activeBookId);
    const matchesSearch = `${chapter.title} ${chapter.preview}`
      .toLowerCase()
      .includes(searchTerm.trim().toLowerCase());
    const matchesStart = !chapterStart || chapter.chapter_number >= Number(chapterStart);
    const matchesEnd = !chapterEnd || chapter.chapter_number <= Number(chapterEnd);

    return (
      matchesBook &&
      matchesSearch &&
      matchesStart &&
      matchesEnd &&
      chapterMatchesStatus(chapter, statusFilter)
    );
  });
  const selectedChapter =
    chapters.find((chapter) => chapter.id === selectedChapterId) || filteredChapters[0] || null;
  const isSingleBookView = activeBookId !== "all";

  return (
    <div className="workspace-page chapter-page">
      <div className="workspace-page-header">
        <div>
          <h1>Chapters</h1>
          <p>Inspect parsed chapters by book before extraction and review.</p>
        </div>
      </div>

      <section className="workspace-page-body chapter-workspace-grid">
        <div className="admin-panel chapter-list-panel">
          <div className="chapter-filter-grid">
            <label>
              Book
              <select value={activeBookId} onChange={(event) => setActiveBookId(event.target.value)}>
                <option value="all">All books</option>
                {books.map((book) => (
                  <option key={book.id} value={book.id}>
                    {bookOptionLabel(book)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Start
              <input
                min="1"
                type="number"
                value={chapterStart}
                onChange={(event) => setChapterStart(event.target.value)}
                placeholder="Any"
              />
            </label>
            <label>
              End
              <input
                min="1"
                type="number"
                value={chapterEnd}
                onChange={(event) => setChapterEnd(event.target.value)}
                placeholder="Any"
              />
            </label>
            <label>
              Review
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option>
                <option value="pending">Pending review</option>
                <option value="warnings">Warnings</option>
              </select>
            </label>
            <label className="chapter-search-field">
              Search
              <input
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search title or preview..."
              />
            </label>
          </div>

          <div className="admin-section-header">
            <h2>Parsed Chapters</h2>
            <span>{filteredChapters.length} shown</span>
          </div>

          <div className="chapter-row-list">
            {filteredChapters.map((chapter) => (
              <button
                className={selectedChapter?.id === chapter.id ? "chapter-list-row active" : "chapter-list-row"}
                key={chapter.id}
                type="button"
                onClick={() => setSelectedChapterId(chapter.id)}
              >
                <div className="chapter-list-row-main">
                  {!isSingleBookView ? (
                    <span className="chapter-book-pill">Book {chapter.book?.number || "?"}</span>
                  ) : null}
                  <strong>
                    {chapter.chapter_number}. {chapter.title}
                  </strong>
                  <small>{chapter.preview}</small>
                </div>
                <span className="chapter-list-row-meta">
                  <em>
                    {chapter.pending_review_count || 0} pending · {chapter.warning_count || 0} warnings
                  </em>
                </span>
              </button>
            ))}
            {filteredChapters.length === 0 ? (
              <p className="admin-muted">No chapters match the current filters.</p>
            ) : null}
          </div>
        </div>

        <ChapterPreviewPanel
          chapter={selectedChapter}
          extractingChapterId={extractingChapterId}
          onExtract={onExtractChapter}
          onReview={onOpenReview}
        />
      </section>
    </div>
  );
}
