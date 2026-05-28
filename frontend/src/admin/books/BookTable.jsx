import React from "react";
import { ArrowRight, MoreHorizontal } from "lucide-react";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function relativeTime(value) {
  if (!value) {
    return null;
  }

  const deltaSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  const days = Math.floor(deltaSeconds / 86400);
  const hours = Math.floor((deltaSeconds % 86400) / 3600);
  const minutes = Math.floor((deltaSeconds % 3600) / 60);

  if (days === 1) return "yesterday";
  if (days > 1) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return "just now";
}

function statusTone(status) {
  if (status === "parsed" || status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "processing") return "info";
  if (status === "queued" || status === "pending" || status === "source_replaced") return "warning";
  return "neutral";
}

function formatStatus(status) {
  if (!status) return "Unknown";
  return status.replaceAll("_", " ");
}

function extractionDetails(book) {
  const total = book.chapter_count || 0;
  const extracted = book.extracted_chapter_count || 0;
  const progress = total ? Math.round((extracted / total) * 100) : 0;

  if (book.last_extraction_status === "failed" && book.failed_chapter_number) {
    return {
      label: `Failed at chapter ${book.failed_chapter_number}`,
      detail: `${extracted} / ${total} extracted`,
      progress,
      failed: true,
    };
  }

  return {
    label: `${extracted} / ${total} extracted`,
    detail: total ? `${progress}% coverage` : "No parsed chapters",
    progress,
    failed: false,
  };
}

function activityLabel(book) {
  const extractionTime = relativeTime(book.last_extraction_at);

  if (book.last_extraction_status === "failed" && extractionTime) {
    return `Failed ${extractionTime}`;
  }

  if (book.last_extraction_status === "completed" && extractionTime) {
    return `Extraction completed ${extractionTime}`;
  }

  if (book.last_extraction_status && extractionTime) {
    return `${formatStatus(book.last_extraction_status)} ${extractionTime}`;
  }

  const uploadTime = relativeTime(book.uploaded_at);
  return uploadTime ? `Uploaded ${uploadTime}` : "No activity yet";
}

function fileType(filename) {
  const extension = filename?.split(".").pop()?.toUpperCase();
  return extension || "TXT";
}

export default function BookTable({
  books,
  onEditBook,
  onOpenChapters,
  onReplaceSource,
  onReparseBook,
}) {
  const [openMenuId, setOpenMenuId] = React.useState(null);
  const menuRef = React.useRef(null);

  React.useEffect(() => {
    if (!openMenuId) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (menuRef.current?.contains(event.target)) {
        return;
      }

      setOpenMenuId(null);
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setOpenMenuId(null);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openMenuId]);

  return (
    <div className="admin-table book-table">
      <div className="admin-table-row admin-table-head">
        <span>Book</span>
        <span>Title</span>
        <span>Source File</span>
        <span>Chapters</span>
        <span>Parsing</span>
        <span>Extraction Coverage</span>
        <span>Last Activity</span>
        <span>Actions</span>
      </div>

      {books.map((book) => {
        const extraction = extractionDetails(book);

        return (
          <div className="admin-table-row book-table-row" key={book.id}>
            <strong className="book-number">{book.number}</strong>

            <div className="book-title-cell">
              <strong title={book.title}>{book.title}</strong>
            </div>

            <div className="book-source-cell">
              <span className="book-file-badge">{fileType(book.source_filename)}</span>
              <span className="admin-truncate" title={book.source_filename || "No source file"}>
                {book.source_filename || "No source file"}
              </span>
            </div>

            <span className="book-chapter-count">{book.chapter_count || 0}</span>

            <StatusBadge tone={statusTone(book.parsing_status)}>
              {formatStatus(book.parsing_status)}
            </StatusBadge>

            <div className={`book-extraction-cell ${extraction.failed ? "failed" : ""}`}>
              <strong>{extraction.label}</strong>
              <ProgressBar value={extraction.progress} />
              <small>{extraction.detail}</small>
            </div>

            <span className="book-activity-cell">{activityLabel(book)}</span>

            <div className="book-actions" ref={openMenuId === book.id ? menuRef : null}>
              <button
                className="admin-secondary-button"
                type="button"
                onClick={() => onOpenChapters(book)}
              >
                Chapters
                <ArrowRight aria-hidden="true" size={16} strokeWidth={1.9} />
              </button>
              <button
                className="admin-icon-button book-more-button"
                type="button"
                aria-label={`More actions for ${book.title}`}
                aria-expanded={openMenuId === book.id}
                onClick={() => setOpenMenuId((currentId) => currentId === book.id ? null : book.id)}
              >
                <MoreHorizontal aria-hidden="true" size={17} strokeWidth={1.9} />
              </button>
              {openMenuId === book.id ? (
                <div className="book-action-menu">
                  <button type="button" onClick={() => { setOpenMenuId(null); onEditBook(book); }}>
                    Edit Book
                  </button>
                  <button
                    type="button"
                    disabled={!book.can_reparse}
                    title={
                      book.can_reparse
                        ? "Replace the stored source file without reparsing."
                        : "Disabled because this book has extracted or review-linked data."
                    }
                    onClick={() => { setOpenMenuId(null); onReplaceSource(book); }}
                  >
                    Replace Source File
                  </button>
                  <button
                    type="button"
                    disabled={!book.can_reparse}
                    title={
                      book.can_reparse
                        ? "Delete parsed chapters and parse the current source again."
                        : "Disabled because this book has extracted or review-linked data."
                    }
                    onClick={() => { setOpenMenuId(null); onReparseBook(book); }}
                  >
                    Reparse Book
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
