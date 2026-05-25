import React from "react";
import EmptyState from "../components/EmptyState.jsx";
import BookTable from "./BookTable.jsx";
import BookUploadModal from "./BookUploadModal.jsx";

export default function BooksPage({ books, novel, onOpenChapters, onUploadBook }) {
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);
  const nextNumber = Math.max(0, ...books.map((book) => book.number || 0)) + 1;

  async function handleUpload(formData) {
    await onUploadBook(formData);
    setIsUploadOpen(false);
  }

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

      <div className="workspace-page-body">
        <section className="admin-panel">
          <div className="admin-section-header">
            <h2>Book Library</h2>
            <span>{books.length} books</span>
          </div>

          {books.length === 0 ? (
            <EmptyState
              title="No books uploaded"
              message="Upload a source text file to parse chapters into this novel workspace."
              action={<button type="button" onClick={() => setIsUploadOpen(true)}>Upload Book</button>}
            />
          ) : (
            <BookTable books={books} onOpenChapters={onOpenChapters} />
          )}
        </section>
      </div>

      {isUploadOpen ? (
        <BookUploadModal
          nextNumber={nextNumber}
          onClose={() => setIsUploadOpen(false)}
          onUpload={handleUpload}
        />
      ) : null}
    </div>
  );
}
