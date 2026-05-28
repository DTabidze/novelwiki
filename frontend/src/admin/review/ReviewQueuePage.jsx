import React from "react";
import { useNavigate } from "react-router-dom";
import {
  ClipboardCheck,
  Download,
  FileText,
  Gauge,
  Package,
  TriangleAlert,
  Users,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";
import StatCard from "../components/StatCard.jsx";
import ReviewBookList from "./ReviewBookList.jsx";
import ReviewChapterGroup from "./ReviewChapterGroup.jsx";
import ReviewDetailPanel from "./ReviewDetailPanel.jsx";
import ReviewFilters from "./ReviewFilters.jsx";
import {
  flattenReviewData,
  recordKey,
  reviewTitle,
  reviewWarnings,
  sourceChapter,
} from "./reviewUtils.js";

function parseChapterRange(value) {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const rangeMatch = trimmed.match(/^(\d+)\s*-\s*(\d+)$/);
  if (rangeMatch) {
    return [Number(rangeMatch[1]), Number(rangeMatch[2])].sort((a, b) => a - b);
  }

  const single = Number(trimmed);
  if (Number.isFinite(single)) {
    return [single, single];
  }

  return null;
}

function groupByChapter(items, booksById) {
  const map = new Map();

  items.forEach((item) => {
    const chapter = sourceChapter(item);
    const key = chapter?.id || "unlinked";

    if (!map.has(key)) {
      const book = booksById.get(chapter?.book_id);
      map.set(key, {
        key,
        chapter,
        bookTitle: book ? `Book ${book.number}: ${book.title}` : "Unlinked source",
        items: [],
      });
    }

    map.get(key).items.push(item);
  });

  return Array.from(map.values()).sort((a, b) => {
    const aChapter = a.chapter;
    const bChapter = b.chapter;
    const aBook = booksById.get(aChapter?.book_id)?.number || 9999;
    const bBook = booksById.get(bChapter?.book_id)?.number || 9999;

    if (aBook !== bBook) return aBook - bBook;
    return (aChapter?.chapter_number || 999999) - (bChapter?.chapter_number || 999999);
  });
}

function countPending(items, predicate) {
  return items.filter((item) => item.review_status === "pending" && predicate(item)).length;
}

export default function ReviewQueuePage({
  books,
  chapters,
  extractedData,
  novel,
  onOpenNovelSettings,
  onRefresh,
}) {
  const navigate = useNavigate();
  const allItems = React.useMemo(() => flattenReviewData(extractedData), [extractedData]);
  const booksById = React.useMemo(() => new Map(books.map((book) => [book.id, book])), [books]);
  const [filters, setFilters] = React.useState({
    bookId: "all",
    chapterRange: "",
    typeGroup: "all",
    status: "pending",
    warningsOnly: false,
    search: "",
  });
  const [selectedKey, setSelectedKey] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);

  const filteredItems = React.useMemo(() => {
    const chapterRange = parseChapterRange(filters.chapterRange);
    const search = filters.search.trim().toLowerCase();

    return allItems.filter((item) => {
      const chapter = sourceChapter(item);
      const warnings = reviewWarnings(item);

      if (filters.bookId !== "all" && String(chapter?.book_id) !== String(filters.bookId)) {
        return false;
      }

      if (chapterRange && (!chapter || chapter.chapter_number < chapterRange[0] || chapter.chapter_number > chapterRange[1])) {
        return false;
      }

      if (filters.typeGroup !== "all" && item.typeGroup !== filters.typeGroup) {
        return false;
      }

      if (filters.status !== "all" && item.review_status !== filters.status) {
        return false;
      }

      if (filters.warningsOnly && warnings.length === 0) {
        return false;
      }

      if (search) {
        const haystack = [
          reviewTitle(item),
          item.character_name,
          item.name,
          item.title,
          item.description,
          item.field_name,
          item.proposed_value,
          chapter?.title,
        ].filter(Boolean).join(" ").toLowerCase();

        if (!haystack.includes(search)) {
          return false;
        }
      }

      return true;
    });
  }, [allItems, filters]);

  const groups = React.useMemo(() => groupByChapter(filteredItems, booksById), [filteredItems, booksById]);
  const selectedItem = filteredItems.find((item) => recordKey(item) === selectedKey) || filteredItems[0] || null;

  React.useEffect(() => {
    if (!selectedItem) {
      setSelectedKey("");
      return;
    }

    if (recordKey(selectedItem) !== selectedKey) {
      setSelectedKey(recordKey(selectedItem));
    }
  }, [selectedItem, selectedKey]);

  const pendingItems = allItems.filter((item) => item.review_status === "pending");
  const pendingWarnings = pendingItems.filter((item) => reviewWarnings(item).length > 0).length;
  const countsByBook = pendingItems.reduce(
    (counts, item) => {
      const chapter = sourceChapter(item);
      counts.all += 1;

      if (chapter?.book_id) {
        counts[chapter.book_id] = (counts[chapter.book_id] || 0) + 1;
      }

      return counts;
    },
    { all: 0 }
  );

  function selectBook(bookId) {
    setFilters((current) => ({ ...current, bookId }));
  }

  function selectItem(item) {
    setSelectedKey(recordKey(item));
  }

  function moveSelection(direction) {
    if (filteredItems.length === 0) return;

    const currentIndex = filteredItems.findIndex((item) => recordKey(item) === selectedKey);
    const nextIndex = currentIndex < 0
      ? 0
      : Math.min(Math.max(currentIndex + direction, 0), filteredItems.length - 1);
    setSelectedKey(recordKey(filteredItems[nextIndex]));
  }

  async function updateReviewItem(item, reviewStatus) {
    setIsSaving(true);

    try {
      await fetchJson(`${API_BASE_URL}/admin/review/${item.entityType}/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_status: reviewStatus }),
      });
      await onRefresh?.({ showLoading: false });
    } finally {
      setIsSaving(false);
    }
  }

  const summaryCards = [
    { label: "Total Pending", value: pendingItems.length, detail: "items", color: "orange", Icon: ClipboardCheck },
    { label: "Characters", value: countPending(allItems, (item) => item.typeGroup === "characters"), detail: "items", color: "purple", Icon: Users },
    { label: "Metadata", value: countPending(allItems, (item) => item.typeGroup === "metadata"), detail: "items", color: "blue", Icon: FileText },
    { label: "Progression", value: countPending(allItems, (item) => item.typeGroup === "progression"), detail: "items", color: "green", Icon: Gauge },
    { label: "Skills & Items", value: countPending(allItems, (item) => item.typeGroup === "skills_items"), detail: "items", color: "orange", Icon: Package },
    { label: "Warnings", value: pendingWarnings, detail: "items", color: "red", Icon: TriangleAlert },
  ];

  return (
    <section className="workspace-page review-page">
      <header className="workspace-page-header">
        <div>
          <h1>Review Queue</h1>
          <p>Review and approve extracted content before it becomes public wiki data.</p>
        </div>
        <div className="admin-header-actions">
          <button type="button" className="admin-secondary-button">
            <Download size={16} /> Export Review Report
          </button>
          <button type="button" className="admin-secondary-button" onClick={() => window.open(`/wiki/novels/${novel?.id}`, "_blank")}>
            View Novel
          </button>
          <button type="button" onClick={onOpenNovelSettings}>Novel Settings</button>
        </div>
      </header>

      <div className="workspace-page-body review-page-body">
        <div className="admin-stat-grid review-stat-grid">
          {summaryCards.map((card) => (
            <StatCard
              key={card.label}
              label={card.label}
              value={card.value}
              detail={card.detail}
              tone={card.color}
              icon={card.Icon}
            />
          ))}
        </div>

        <ReviewFilters books={books} filters={filters} onChange={setFilters} />

        <div className="review-workspace-grid">
          <ReviewBookList
            books={books}
            countsByBook={countsByBook}
            selectedBookId={filters.bookId}
            onSelectBook={selectBook}
          />

          <main className="review-feed-panel admin-panel">
            <div className="review-panel-title">
              <div>
                <h2>
                  {filters.bookId === "all"
                    ? "All Review Items"
                    : `Book ${booksById.get(Number(filters.bookId))?.number || filters.bookId}: ${booksById.get(Number(filters.bookId))?.title || ""}`}
                </h2>
                <span>{filteredItems.length} shown</span>
              </div>
            </div>

            <div className="review-feed-list">
              {groups.length === 0 ? (
                <div className="review-empty-feed">
                  <strong>No review items match the current filters.</strong>
                  <p>Try a different book, status, type, or search term.</p>
                </div>
              ) : (
                groups.map((group) => (
                  <ReviewChapterGroup
                    key={group.key}
                    group={group}
                    selectedKey={selectedKey}
                    onSelect={selectItem}
                  />
                ))
              )}
            </div>

            <footer className="review-feed-footer">
              <span>Showing {Math.min(filteredItems.length, 1)} to {filteredItems.length} of {filteredItems.length} items</span>
              <div>
                <button type="button" className="admin-icon-button">1</button>
                <button type="button" className="admin-icon-button admin-secondary-button">2</button>
                <button type="button" className="admin-icon-button admin-secondary-button">3</button>
              </div>
            </footer>
          </main>

          <ReviewDetailPanel
            item={selectedItem}
            isSaving={isSaving}
            onApprove={(item) => updateReviewItem(item, "approved")}
            onReject={(item) => updateReviewItem(item, "rejected")}
            onSkip={() => moveSelection(1)}
            onClose={() => setSelectedKey("")}
            onNext={() => moveSelection(1)}
            onPrevious={() => moveSelection(-1)}
          />
        </div>
      </div>
    </section>
  );
}
