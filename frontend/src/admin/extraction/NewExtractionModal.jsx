import React from "react";
import { chapterLabel } from "../../utils/wikiFormat.js";

function bookOptionLabel(book) {
  const defaultTitle = `Book ${book.number}`;
  return !book.title || book.title === defaultTitle ? defaultTitle : `${defaultTitle}: ${book.title}`;
}

export default function NewExtractionModal({
  books,
  chapters,
  extractionRuns = [],
  initialValues = null,
  onClose,
  onStart,
}) {
  const firstParsedBook = books.find((book) => (book.chapter_count || 0) > 0) || books[0];
  const [bookId, setBookId] = React.useState(initialValues?.bookId || (firstParsedBook?.id ? String(firstParsedBook.id) : ""));
  const [chapterEnd, setChapterEnd] = React.useState(initialValues?.chapterEnd || "");
  const [chapterId, setChapterId] = React.useState("");
  const [chapterStart, setChapterStart] = React.useState(initialValues?.chapterStart || "");
  const [error, setError] = React.useState("");
  const [isStarting, setIsStarting] = React.useState(false);
  const [scopeType, setScopeType] = React.useState(initialValues?.scopeType || "book");

  const bookChapters = chapters
    .filter((chapter) => String(chapter.book_id) === bookId)
    .sort((a, b) => a.chapter_number - b.chapter_number);
  const parsedBooks = books.filter((book) => (book.chapter_count || 0) > 0);
  const selectedBook = books.find((book) => String(book.id) === bookId);
  const novelChapterCount = chapters.length;
  const firstBookChapter = bookChapters[0] || null;
  const lastBookChapter = bookChapters[bookChapters.length - 1] || null;
  const extractedChapterIds = React.useMemo(() => {
    const ids = new Set();

    extractionRuns.forEach((run) => {
      (run.run_chapters || []).forEach((runChapter) => {
        if (runChapter.status === "completed" && runChapter.chapter_id) {
          ids.add(runChapter.chapter_id);
        }
      });
    });

    return ids;
  }, [extractionRuns]);
  const firstUnextractedChapter = bookChapters.find((chapter) => !extractedChapterIds.has(chapter.id)) || null;
  const bookRangeLabel = firstBookChapter && lastBookChapter
    ? firstBookChapter.chapter_number === lastBookChapter.chapter_number
      ? `Chapter ${firstBookChapter.chapter_number}`
      : `Chapters ${firstBookChapter.chapter_number}-${lastBookChapter.chapter_number}`
    : "";

  React.useEffect(() => {
    setChapterId("");
  }, [bookId, scopeType]);

  React.useEffect(() => {
    if (scopeType !== "chapter_range" || !firstBookChapter || !lastBookChapter) return;

    const defaultStart = initialValues?.chapterStart
      ? clampChapterRangeValue(initialValues.chapterStart)
      : String((firstUnextractedChapter || firstBookChapter).chapter_number);

    setChapterStart(defaultStart);
    setChapterEnd(initialValues?.chapterEnd ? clampChapterRangeValue(initialValues.chapterEnd) : String(lastBookChapter.chapter_number));
  }, [bookId, firstBookChapter, firstUnextractedChapter, initialValues, lastBookChapter, scopeType]);

  function clampChapterRangeValue(value) {
    if (!firstBookChapter || !lastBookChapter || value === "") return value;

    const numberValue = Number(value);

    if (!Number.isFinite(numberValue)) return value;

    return String(Math.min(
      Math.max(numberValue, firstBookChapter.chapter_number),
      lastBookChapter.chapter_number,
    ));
  }

  function validateChapterRange() {
    if (scopeType !== "chapter_range") return true;

    const startNumber = Number(chapterStart);
    const endNumber = Number(chapterEnd);

    if (!chapterStart || !chapterEnd || !Number.isFinite(startNumber) || !Number.isFinite(endNumber)) {
      setError("Enter a start and end chapter inside the selected book.");
      return false;
    }

    if (startNumber > endNumber) {
      setError("Chapter start cannot be greater than chapter end.");
      return false;
    }

    if (
      firstBookChapter
      && lastBookChapter
      && (startNumber < firstBookChapter.chapter_number || endNumber > lastBookChapter.chapter_number)
    ) {
      setError(`${bookOptionLabel(selectedBook)} contains ${bookRangeLabel}. Choose a chapter range inside this book.`);
      return false;
    }

    return true;
  }

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

    if (!validateChapterRange()) {
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
          <>
            <div className="book-upload-grid">
              <label>
                Start
                <input
                  min={firstBookChapter?.chapter_number || 1}
                  max={lastBookChapter?.chapter_number || undefined}
                  type="number"
                  value={chapterStart}
                  disabled={isStarting}
                  onBlur={() => setChapterStart((value) => clampChapterRangeValue(value))}
                  onChange={(event) => {
                    setChapterStart(event.target.value);
                    setError("");
                  }}
                  placeholder="First chapter"
                />
              </label>
              <label>
                End
                <input
                  min={firstBookChapter?.chapter_number || 1}
                  max={lastBookChapter?.chapter_number || undefined}
                  type="number"
                  value={chapterEnd}
                  disabled={isStarting}
                  onBlur={() => setChapterEnd((value) => clampChapterRangeValue(value))}
                  onChange={(event) => {
                    setChapterEnd(event.target.value);
                    setError("");
                  }}
                  placeholder="Last chapter"
                />
              </label>
            </div>
            {bookRangeLabel ? (
              <p className="admin-inline-warning extraction-range-note">
                {bookOptionLabel(selectedBook)} contains {bookRangeLabel}. Range extraction uses these novel chapter numbers.
                {" "}
                {firstUnextractedChapter
                  ? `Next unextracted chapter: Chapter ${firstUnextractedChapter.chapter_number}.`
                  : "All parsed chapters in this book have completed extraction."}
              </p>
            ) : null}
          </>
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
                  {chapterLabel(chapter)}
                  {extractedChapterIds.has(chapter.id) ? " (extracted)" : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scopeType === "book" && bookChapters.length ? (
          <p className="admin-inline-warning extraction-range-note">
            This will extract {bookChapters.length} chapters from the selected book.
          </p>
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
