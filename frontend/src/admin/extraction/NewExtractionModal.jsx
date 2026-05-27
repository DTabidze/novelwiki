import React from "react";

function bookOptionLabel(book) {
  const defaultTitle = `Book ${book.number}`;
  return !book.title || book.title === defaultTitle ? defaultTitle : `${defaultTitle}: ${book.title}`;
}

export default function NewExtractionModal({ books, chapters, onClose, onStart }) {
  const [bookId, setBookId] = React.useState(books[0]?.id ? String(books[0].id) : "");
  const [chapterEnd, setChapterEnd] = React.useState("");
  const [chapterId, setChapterId] = React.useState("");
  const [chapterStart, setChapterStart] = React.useState("");
  const [scopeType, setScopeType] = React.useState("book");

  const bookChapters = chapters.filter((chapter) => String(chapter.book_id) === bookId);

  function submit(event) {
    event.preventDefault();

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

    onStart(payload);
    onClose();
  }

  return (
    <div className="admin-modal-backdrop">
      <form className="admin-modal" onSubmit={submit}>
        <div className="admin-modal-header">
          <div>
            <h2>New Extraction</h2>
            <p>Choose a safe extraction scope.</p>
          </div>
          <button className="admin-icon-button" type="button" onClick={onClose}>x</button>
        </div>

        <label>
          Scope
          <select value={scopeType} onChange={(event) => setScopeType(event.target.value)}>
            <option value="book">Entire book</option>
            <option value="chapter_range">Chapter range</option>
            <option value="single_chapter">Single chapter</option>
            <option value="novel">Entire novel</option>
            <option value="retry_failed">Retry failed chapters</option>
          </select>
        </label>

        {["book", "chapter_range"].includes(scopeType) ? (
          <label>
            Book
            <select value={bookId} onChange={(event) => setBookId(event.target.value)} required>
              {books.map((book) => (
                <option key={book.id} value={book.id}>
                  {bookOptionLabel(book)}
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
                onChange={(event) => setChapterEnd(event.target.value)}
                placeholder="Last chapter"
              />
            </label>
          </div>
        ) : null}

        {scopeType === "single_chapter" ? (
          <label>
            Chapter
            <select value={chapterId} onChange={(event) => setChapterId(event.target.value)} required>
              <option value="">Select chapter</option>
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  Book {chapter.book?.number || "?"} · Chapter {chapter.chapter_number}: {chapter.title}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scopeType === "book" && bookChapters.length ? (
          <p className="admin-muted">This will extract {bookChapters.length} chapters from the selected book.</p>
        ) : null}

        <div className="admin-modal-actions">
          <button className="admin-secondary-button" type="button" onClick={onClose}>Cancel</button>
          <button type="submit">Start Extraction</button>
        </div>
      </form>
    </div>
  );
}
