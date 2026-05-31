import React from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, CheckCircle2, FileCheck2, Files } from "lucide-react";
import EmptyState from "../components/EmptyState.jsx";
import StatCard from "../components/StatCard.jsx";
import BookTable from "./BookTable.jsx";
import EditBookModal from "./EditBookModal.jsx";
import BookUploadModal from "./BookUploadModal.jsx";
import ReparseBookModal from "./ReparseBookModal.jsx";
import ReplaceBookSourceModal from "./ReplaceBookSourceModal.jsx";

export default function BooksPage({
  books,
  novel,
  onOpenChapters,
  onUploadBook,
  onUpdateBook,
  onReplaceBookSource,
  onReparseBook,
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);
  const [editingBook, setEditingBook] = React.useState(null);
  const [replacingBook, setReplacingBook] = React.useState(null);
  const [reparsingBook, setReparsingBook] = React.useState(null);
  const [toast, setToast] = React.useState(null);
  const nextNumber = Math.max(0, ...books.map((book) => book.number || 0)) + 1;
  const totalChapters = books.reduce((total, book) => total + (book.chapter_count || 0), 0);
  const parsedBooks = books.filter((book) => book.parsing_status === "parsed").length;
  const extractedChapters = books.reduce(
    (total, book) => total + (book.extracted_chapter_count || 0),
    0
  );
  const extractionCoverage = totalChapters
    ? Math.round((extractedChapters / totalChapters) * 100)
    : 0;

  async function handleUpload(formData) {
    const data = await onUploadBook(formData);
    setIsUploadOpen(false);
    setSearchParams({});
    setToast({
      tone: "success",
      message: `Book uploaded and parsed successfully. ${data.chapter_count} chapters created.`,
    });
  }

  async function handleUpdateBook(book, payload) {
    const data = await onUpdateBook(book.id, payload);
    setEditingBook(null);
    setToast({
      tone: "success",
      message: `${data.book.title} updated successfully.`,
    });
  }

  async function handleReplaceSource(book, formData) {
    const data = await onReplaceBookSource(book.id, formData);
    setReplacingBook(null);
    setToast({
      tone: "success",
      message: `Source file replaced for ${data.book.title}. ${data.deleted_chapter_count || 0} parsed chapters cleared.`,
    });
  }

  async function handleReparseBook(book) {
    const data = await onReparseBook(book.id);
    setReparsingBook(null);
    setToast({
      tone: "success",
      message: `Book reparsed successfully. ${data.chapter_count} chapters created.`,
    });
  }

  React.useEffect(() => {
    if (searchParams.get("upload") === "1") {
      setIsUploadOpen(true);
    }
  }, [searchParams]);

  React.useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  return (
    <div className="workspace-page">
      <div className="workspace-page-header">
        <div>
          <h1>Books</h1>
          <p>Upload and manage source files for {novel?.title || "this novel"}.</p>
        </div>
        <button type="button" onClick={() => setIsUploadOpen(true)}>
          Upload Book
        </button>
      </div>

      <div className="workspace-page-body books-page-body">
        <div className="admin-stat-grid books-stats-row">
          <StatCard
            icon={BookOpen}
            label="Books"
            value={books.length}
            detail="Volumes uploaded"
            tone="blue"
          />
          <StatCard
            icon={Files}
            label="Total Chapters"
            value={totalChapters}
            detail="Parsed from source"
            tone="green"
          />
          <StatCard
            icon={FileCheck2}
            label="Parsed Books"
            value={parsedBooks}
            detail={`${books.length - parsedBooks} waiting`}
            tone="purple"
          />
          <StatCard
            icon={CheckCircle2}
            label="Extraction Coverage"
            value={`${extractionCoverage}%`}
            detail={`${extractedChapters} extracted`}
            tone="orange"
          />
        </div>

        <section className="admin-panel book-library-panel">
          <div className="admin-section-header">
            <div>
              <h2>Source Books</h2>
              <p>Manage uploaded text files and chapter ingestion for this novel.</p>
            </div>
            <span>{books.length} books</span>
          </div>

          {books.length === 0 ? (
            <EmptyState
              title="No books uploaded"
              message="Upload a source text file to parse chapters into this novel workspace."
            />
          ) : (
            <BookTable
              books={books}
              onEditBook={setEditingBook}
              onOpenChapters={onOpenChapters}
              onReplaceSource={setReplacingBook}
              onReparseBook={setReparsingBook}
            />
          )}
        </section>
      </div>

      {isUploadOpen ? (
        <BookUploadModal
          nextNumber={nextNumber}
          onClose={() => {
            setIsUploadOpen(false);
            setSearchParams({});
          }}
          onUpload={handleUpload}
        />
      ) : null}

      {editingBook ? (
        <EditBookModal
          book={editingBook}
          books={books}
          onClose={() => setEditingBook(null)}
          onSave={handleUpdateBook}
        />
      ) : null}

      {replacingBook ? (
        <ReplaceBookSourceModal
          book={replacingBook}
          onClose={() => setReplacingBook(null)}
          onReplace={handleReplaceSource}
        />
      ) : null}

      {reparsingBook ? (
        <ReparseBookModal
          book={reparsingBook}
          onClose={() => setReparsingBook(null)}
          onConfirm={handleReparseBook}
        />
      ) : null}

      {toast ? (
        <div className={`admin-toast ${toast.tone}`} role="status">
          {toast.message}
        </div>
      ) : null}
    </div>
  );
}
