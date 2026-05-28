import React from "react";

function bookOptionLabel(book) {
  const defaultTitle = `Book ${book.number}`;
  return !book.title || book.title === defaultTitle ? defaultTitle : `${defaultTitle}: ${book.title}`;
}

function cleanChapterTitle(chapter) {
  const prefix = new RegExp(`^chapter\\s+${chapter.chapter_number}\\s*:?\\s*`, "i");
  return (chapter.title || "").replace(prefix, "").trim() || `Chapter ${chapter.chapter_number}`;
}

export default function NewExtractionModal({ books, chapters, onClose, onStart }) {
  const firstParsedBook = books.find((book) => (book.chapter_count || 0) > 0) || books[0];
  const [bookId, setBookId] = React.useState(firstParsedBook?.id ? String(firstParsedBook.id) : "");
  const [chapterEnd, setChapterEnd] = React.useState("");
  const [chapterId, setChapterId] = React.useState("");
  const [chapterStart, setChapterStart] = React.useState("");
  const [error, setError] = React.useState("");
  const [isStarting, setIsStarting] = React.useState(false);
  const [scopeType, setScopeType] = React.useState("book");

  const bookChapters = chapters.filter((chapter) => String(chapter.book_id) === bookId);
  const parsedBooks = books.filter((book) => (book.chapter_count || 0) > 0);
  const selectedBook = books.find((book) => String(book.id) === bookId);
  const novelChapterCount = chapters.length;

  React.useEffect(() => {
    setChapterId("");
  }, [bookId, scopeType]);

  async function submit(event) {
    event.preventDefault();
    setError("");

    if (["book", "chapter_range"].includes(scopeType) && (!selectedBook || bookChapters.length === 0)) {
      setError("This book has no parsed chapters yet. Reparse the book before starting extraction.");
      return;
    }

    if (scopeType === "single_chapter" && (!selectedBook || bookChapters.length === 0)) {
      setError("This book has no parsed chapters yet. Reparse the book before starting extraction.");
      return;
    }

    if (scopeType === "single_chapter" && !chapterId) {
      setError("Select a chapter number before starting extraction.");
      return;
    }

    if (scopeType === "novel" && novelChapterCount === 0) {
      setError("This novel has no parsed chapters yet. Upload and parse a book before starting extraction.");
      return;
    }

    const payload = { scope_type: scopeType };

    if (scopeType === "single_chapter") {
      payload.chapter_id = Number(chapterId);
    }

    if (scopeType === "chapter_range") {
      payload.book_id = Number(bookId);
      payload.chapter_start = chapterStart ? Number(chapterStart) : null;
      payload.chapter_end = chapterEnd ? Number(chapterEnd) : null;
    }

    if (scopeType === "book") {
      payload.book_id = Number(bookId);
    }

    setIsStarting(true);

    try {
      await onStart(payload);
      onClose();
    } catch (startError) {
      setError(startError.message || "Could not start extraction.");
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal extraction-modal" onSubmit={submit}>
        <div className="admin-modal-header">
          <div>
            <h2>New Extraction</h2>
            <p>Choose a safe extraction scope.</p>
          </div>
          <button className="admin-icon-button" disabled={isStarting} type="button" onClick={onClose}>x</button>
        </div>

        <label>
          Scope
          <select
            disabled={isStarting}
            value={scopeType}
            onChange={(event) => {
              setScopeType(event.target.value);
              setError("");
            }}
          >
            <option value="book">Entire book</option>
            <option value="chapter_range">Chapter range</option>
            <option value="single_chapter">Single chapter</option>
            <option value="novel">Entire novel</option>
            <option value="retry_failed">Retry failed chapters</option>
          </select>
        </label>

        {["book", "chapter_range", "single_chapter"].includes(scopeType) ? (
          <label>
            Book
            <select
              value={bookId}
              disabled={isStarting}
              onChange={(event) => {
                setBookId(event.target.value);
                setError("");
              }}
              required
            >
              {books.map((book) => (
                <option key={book.id} value={book.id} disabled={(book.chapter_count || 0) === 0}>
                  {bookOptionLabel(book)}{(book.chapter_count || 0) === 0 ? " - needs reparse" : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scopeType === "chapter_range" ? (
          <div className="book-upload-grid">
            <label>
              Start
              <input
                min="1"
                type="number"
                value={chapterStart}
                disabled={isStarting}
                onChange={(event) => setChapterStart(event.target.value)}
                placeholder="First chapter"
              />
            </label>
            <label>
              End
              <input
                min="1"
                type="number"
                value={chapterEnd}
                disabled={isStarting}
                onChange={(event) => setChapterEnd(event.target.value)}
                placeholder="Last chapter"
              />
            </label>
          </div>
        ) : null}

        {scopeType === "single_chapter" ? (
          <label>
            Chapter number
            <select
              value={chapterId}
              disabled={isStarting}
              onChange={(event) => {
                setChapterId(event.target.value);
                setError("");
              }}
              required
            >
              <option value="">Select chapter number</option>
              {bookChapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  Chapter {chapter.chapter_number}: {cleanChapterTitle(chapter)}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scopeType === "book" && bookChapters.length ? (
          <p className="admin-muted">This will extract {bookChapters.length} chapters from the selected book.</p>
        ) : null}

        {["book", "chapter_range", "single_chapter"].includes(scopeType) && selectedBook && bookChapters.length === 0 ? (
          <div className="admin-inline-warning">
            {bookOptionLabel(selectedBook)} has no parsed chapters. Reparse the book before extraction.
          </div>
        ) : null}

        {scopeType === "novel" && parsedBooks.length < books.length ? (
          <div className="admin-inline-warning">
            Books without parsed chapters will be skipped because there is nothing to extract.
          </div>
        ) : null}

        {error ? <div className="admin-inline-error">{error}</div> : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" disabled={isStarting} type="button" onClick={onClose}>Cancel</button>
          <button
            disabled={
              isStarting
              || (["book", "chapter_range", "single_chapter"].includes(scopeType) && (!selectedBook || bookChapters.length === 0))
              || (scopeType === "single_chapter" && !chapterId)
              || (scopeType === "novel" && novelChapterCount === 0)
            }
            type="submit"
          >
            {isStarting ? "Starting..." : "Start Extraction"}
          </button>
        </div>
      </form>
    </div>
  );
}
