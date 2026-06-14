import React from "react";
import { useSearchParams } from "react-router-dom";
import {
  ClipboardCheck,
  Download,
  FileText,
  Gauge,
  Package,
  TriangleAlert,
  Users,
  X,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";
import AdminNoticeModal from "../components/AdminNoticeModal.jsx";
import ReviewChapterGroup from "./ReviewChapterGroup.jsx";
import ReviewContextModal from "./ReviewContextModal.jsx";
import ReviewDetailPanel from "./ReviewDetailPanel.jsx";
import ReviewEditProposalModal from "./ReviewEditProposalModal.jsx";
import ReviewFilters from "./ReviewFilters.jsx";
import {
  flattenReviewData,
  recordKey,
  reviewTitle,
  reviewWarnings,
  sourceChapter,
} from "./reviewUtils.js";

const CHAPTER_GROUP_PAGE_SIZE = 10;
const CHAPTER_ITEM_PREVIEW_LIMIT = 8;
const VALID_REVIEW_STATUSES = new Set(["pending", "approved", "rejected", "all"]);
const DEFAULT_REVIEW_FILTERS = {
  bookId: "all",
  chapterRange: "",
  typeGroup: "all",
  status: "pending",
  warningsOnly: false,
  search: "",
};

function isReviewConflict(error) {
  return error?.status === 409 || error?.status === 404;
}

function reviewConflictMessage(error) {
  if (error?.status === 404) {
    return "This review item is no longer available. Refresh to continue.";
  }

  return error?.message || "This review item was changed by another admin. Refresh to continue.";
}

function filtersFromSearchParams(searchParams) {
  const chapterStart = searchParams.get("chapter_start");
  const chapterEnd = searchParams.get("chapter_end");
  const status = searchParams.get("status") || "pending";
  const chapterRange = chapterStart && chapterEnd
    ? chapterStart === chapterEnd
      ? chapterStart
      : `${chapterStart}-${chapterEnd}`
    : "";

  return {
    ...DEFAULT_REVIEW_FILTERS,
    bookId: searchParams.get("book_id") || DEFAULT_REVIEW_FILTERS.bookId,
    chapterRange,
    typeGroup: searchParams.get("type") || DEFAULT_REVIEW_FILTERS.typeGroup,
    status: VALID_REVIEW_STATUSES.has(status) ? status : "pending",
    warningsOnly: searchParams.get("warnings") === "1",
    search: searchParams.get("search") || "",
  };
}

function filtersToSearchParams(filters, source = "") {
  const params = new URLSearchParams();

  if (source) params.set("source", source);
  if (filters.bookId !== DEFAULT_REVIEW_FILTERS.bookId) params.set("book_id", filters.bookId);
  if (filters.chapterRange) {
    const range = parseChapterRange(filters.chapterRange);

    if (range) {
      params.set("chapter_start", String(range[0]));
      params.set("chapter_end", String(range[1]));
    }
  }
  if (filters.typeGroup !== DEFAULT_REVIEW_FILTERS.typeGroup) params.set("type", filters.typeGroup);
  if (filters.status !== DEFAULT_REVIEW_FILTERS.status || source) params.set("status", filters.status);
  if (filters.warningsOnly) params.set("warnings", "1");
  if (filters.search.trim()) params.set("search", filters.search.trim());

  return params;
}

function statusLabel(value) {
  if (value === "all") return "All statuses";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function typeGroupLabel(value) {
  const labels = {
    characters: "Character",
    metadata: "Metadata",
    progression: "Progression",
    skills_items: "Skills & Items",
  };

  return labels[value] || value;
}

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

function chapterGroupKey(group) {
  return String(group.key);
}

function chapterKeyForItem(item) {
  const chapter = sourceChapter(item);
  return chapter?.id ? String(chapter.id) : "unlinked";
}

function pageForChapterGroup(groups, groupKey) {
  const groupIndex = groups.findIndex((group) => chapterGroupKey(group) === groupKey);
  return groupIndex < 0 ? 1 : Math.floor(groupIndex / CHAPTER_GROUP_PAGE_SIZE) + 1;
}

function pageForReviewItem(groups, item) {
  if (!item) return 1;
  return pageForChapterGroup(groups, chapterKeyForItem(item));
}

function countPending(items, predicate) {
  return items.filter((item) => item.review_status === "pending" && predicate(item)).length;
}

function ReviewActiveFilterStrip({
  booksById,
  filters,
  onClearAll,
  onClearExtractionScope,
  onRemoveFilter,
  source,
}) {
  const selectedBook = filters.bookId !== "all" ? booksById.get(Number(filters.bookId)) : null;
  const isExtractionScope = source === "extraction_run";
  const chips = [];

  if (selectedBook) {
    chips.push({ key: "bookId", label: `Book ${selectedBook.number}` });
  }

  if (filters.chapterRange) {
    chips.push({ key: "chapterRange", label: `Chapters ${filters.chapterRange}` });
  }

  if (filters.status !== DEFAULT_REVIEW_FILTERS.status || isExtractionScope) {
    chips.push({ key: "status", label: statusLabel(filters.status) });
  }

  if (filters.typeGroup !== DEFAULT_REVIEW_FILTERS.typeGroup) {
    chips.push({ key: "typeGroup", label: `Type: ${typeGroupLabel(filters.typeGroup)}` });
  }

  if (filters.warningsOnly) {
    chips.push({ key: "warningsOnly", label: "Warnings only" });
  }

  if (filters.search.trim()) {
    chips.push({ key: "search", label: `Search: "${filters.search.trim()}"` });
  }

  if (!chips.length && !isExtractionScope) return null;

  const sourceLabel = [
    selectedBook ? `Book ${selectedBook.number}` : null,
    filters.chapterRange ? `Chapters ${filters.chapterRange}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <section className="review-active-filter-strip" aria-label="Active review filters">
      <div>
        {isExtractionScope ? (
          <strong>Showing items from extraction run{sourceLabel ? `: ${sourceLabel}` : ""}</strong>
        ) : (
          <strong>Filtered by</strong>
        )}
        <div className="review-active-filter-chips">
          {chips.map((chip) => (
            <button key={chip.key} type="button" onClick={() => onRemoveFilter(chip.key)}>
              <span>{chip.label}</span>
              <X aria-hidden="true" size={13} strokeWidth={2} />
            </button>
          ))}
        </div>
      </div>
      <div className="review-active-filter-actions">
        {isExtractionScope && filters.chapterRange ? (
          <button className="admin-secondary-button" type="button" onClick={onClearExtractionScope}>
            Clear extraction scope
          </button>
        ) : null}
        <button className="admin-secondary-button" type="button" onClick={onClearAll}>
          Clear filters
        </button>
      </div>
    </section>
  );
}

export default function ReviewQueuePage({
  books,
  chapters,
  extractedData,
  novel,
  onRefresh,
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const searchSignature = searchParams.toString();
  const reviewSource = searchParams.get("source") || "";
  const allItems = React.useMemo(() => flattenReviewData(extractedData), [extractedData]);
  const booksById = React.useMemo(() => new Map(books.map((book) => [book.id, book])), [books]);
  const persistedSelectionKey = React.useMemo(
    () => `novelwiki-review-selection-${novel?.id || "global"}`,
    [novel?.id]
  );
  const [filters, setFilters] = React.useState(() => filtersFromSearchParams(searchParams));
  const [selectedKey, setSelectedKey] = React.useState(() => window.sessionStorage.getItem(persistedSelectionKey) || "");
  const [isSaving, setIsSaving] = React.useState(false);
  const [expandedChapterKeys, setExpandedChapterKeys] = React.useState(() => new Set());
  const [revealedChapterKeys, setRevealedChapterKeys] = React.useState(() => new Set());
  const [chapterPage, setChapterPage] = React.useState(1);
  const [contextEvidence, setContextEvidence] = React.useState(null);
  const [editingItem, setEditingItem] = React.useState(null);
  const [editError, setEditError] = React.useState("");
  const [reviewConflict, setReviewConflict] = React.useState(null);
  const feedListRef = React.useRef(null);
  const scrollModeRef = React.useRef("nearest");
  const pendingSelectionKeyRef = React.useRef(undefined);
  const filterChangeSelectionKeyRef = React.useRef("");
  const filterSignature = `${filters.bookId}|${filters.chapterRange}|${filters.typeGroup}|${filters.status}|${filters.warningsOnly}|${filters.search}`;

  React.useEffect(() => {
    setFilters(filtersFromSearchParams(new URLSearchParams(searchSignature)));
  }, [searchSignature]);

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
  const orderedItems = React.useMemo(() => groups.flatMap((group) => group.items), [groups]);
  const firstQueueItem = orderedItems[0] || null;
  const selectedItem = orderedItems.find((item) => recordKey(item) === selectedKey) || null;
  const selectedChapter = selectedItem ? sourceChapter(selectedItem) : null;
  const selectedGroupKey = selectedChapter?.id ? String(selectedChapter.id) : "unlinked";
  const totalChapterPages = Math.max(1, Math.ceil(groups.length / CHAPTER_GROUP_PAGE_SIZE));
  const clampedChapterPage = Math.min(chapterPage, totalChapterPages);
  const visibleGroups = groups.slice(
    (clampedChapterPage - 1) * CHAPTER_GROUP_PAGE_SIZE,
    clampedChapterPage * CHAPTER_GROUP_PAGE_SIZE
  );
  const firstVisibleGroup = visibleGroups[0];
  const lastVisibleGroup = visibleGroups[visibleGroups.length - 1];
  const firstQueueItemKey = firstQueueItem ? recordKey(firstQueueItem) : "";
  const selectedIndex = selectedItem
    ? orderedItems.findIndex((item) => recordKey(item) === recordKey(selectedItem))
    : -1;
  const isFirstSelected = selectedIndex <= 0;
  const isLastSelected = selectedIndex < 0 || selectedIndex >= orderedItems.length - 1;

  React.useEffect(() => {
    pendingSelectionKeyRef.current = undefined;
    const candidateSelectionKey = filterChangeSelectionKeyRef.current || selectedKey;
    const existingSelectionIsVisible = candidateSelectionKey
      && orderedItems.some((item) => recordKey(item) === candidateSelectionKey);
    const nextSelectedKey = existingSelectionIsVisible ? candidateSelectionKey : firstQueueItemKey;
    setRevealedChapterKeys(new Set());

    if (nextSelectedKey) {
      const nextItem = orderedItems.find((item) => recordKey(item) === nextSelectedKey) || firstQueueItem;
      const firstChapter = sourceChapter(nextItem);
      const firstGroupKey = firstChapter?.id ? String(firstChapter.id) : "unlinked";

      setChapterPage(pageForReviewItem(groups, nextItem));
      setSelectedKey(nextSelectedKey);
      setExpandedChapterKeys(new Set([firstGroupKey]));
    } else {
      setChapterPage(1);
      setSelectedKey("");
      setExpandedChapterKeys(new Set());
    }
  }, [filterSignature]);

  React.useEffect(() => {
    filterChangeSelectionKeyRef.current = selectedKey;

    if (selectedKey) {
      window.sessionStorage.setItem(persistedSelectionKey, selectedKey);
    } else {
      window.sessionStorage.removeItem(persistedSelectionKey);
    }
  }, [persistedSelectionKey, selectedKey]);

  React.useEffect(() => {
    const pendingSelectionKey = pendingSelectionKeyRef.current;

    if (pendingSelectionKey !== undefined) {
      pendingSelectionKeyRef.current = undefined;

      const pendingItem = pendingSelectionKey
        ? orderedItems.find((item) => recordKey(item) === pendingSelectionKey)
        : null;

      if (pendingItem) {
        setChapterPage(pageForReviewItem(groups, pendingItem));
        setSelectedKey(pendingSelectionKey);
      } else if (!pendingSelectionKey) {
        setChapterPage(1);
        setSelectedKey("");
      } else {
        setChapterPage(firstQueueItem ? pageForReviewItem(groups, firstQueueItem) : 1);
        setSelectedKey(firstQueueItemKey);
      }

      return;
    }

    if (selectedKey && orderedItems.some((item) => recordKey(item) === selectedKey)) {
      return;
    }

    if (firstQueueItemKey) {
      setChapterPage(firstQueueItem ? pageForReviewItem(groups, firstQueueItem) : 1);
      setSelectedKey(firstQueueItemKey);
    } else if (selectedKey) {
      setChapterPage(1);
      setSelectedKey("");
    }
  }, [firstQueueItemKey, orderedItems, selectedKey]);

  React.useEffect(() => {
    if (groups.length === 0) {
      setExpandedChapterKeys(new Set());
      return;
    }

    const keyToExpand = selectedItem
      ? selectedGroupKey
      : chapterGroupKey(groups[0]);

    setExpandedChapterKeys((current) => {
      if (current.has(keyToExpand)) return current;
      const next = new Set(current);
      next.add(keyToExpand);
      return next;
    });
  }, [groups, selectedGroupKey, selectedItem]);

  React.useEffect(() => {
    if (!selectedItem) return;

    const selectedGroup = groups.find((group) => chapterGroupKey(group) === selectedGroupKey);
    if (!selectedGroup) return;

    const selectedItemIndex = selectedGroup.items.findIndex((item) => recordKey(item) === recordKey(selectedItem));
    if (selectedItemIndex < CHAPTER_ITEM_PREVIEW_LIMIT) return;

    setRevealedChapterKeys((current) => {
      if (current.has(selectedGroupKey)) return current;
      const next = new Set(current);
      next.add(selectedGroupKey);
      return next;
    });
  }, [groups, selectedGroupKey, selectedItem]);

  React.useEffect(() => {
    if (!selectedKey) return;

    const scrollMode = scrollModeRef.current;
    const frame = window.requestAnimationFrame(() => {
      const scrollContainer = feedListRef.current;
      const selectedElement = document.getElementById(`review-item-${selectedKey}`);
      if (!scrollContainer || !selectedElement) return;

      const containerRect = scrollContainer.getBoundingClientRect();
      const itemRect = selectedElement.getBoundingClientRect();
      const isFullyVisible = itemRect.top >= containerRect.top && itemRect.bottom <= containerRect.bottom;

      if (isFullyVisible && scrollMode === "nearest") {
        scrollModeRef.current = "nearest";
        return;
      }

      const currentScrollTop = scrollContainer.scrollTop;
      const itemTop = itemRect.top - containerRect.top + currentScrollTop;
      const itemBottom = itemTop + selectedElement.offsetHeight;
      let nextScrollTop = currentScrollTop;

      if (scrollMode === "center") {
        nextScrollTop = itemTop - (scrollContainer.clientHeight / 2) + (selectedElement.offsetHeight / 2);
      } else if (itemRect.top < containerRect.top) {
        nextScrollTop = itemTop;
      } else if (itemRect.bottom > containerRect.bottom) {
        nextScrollTop = itemBottom - scrollContainer.clientHeight;
      }

      scrollContainer.scrollTo({
        top: Math.max(0, nextScrollTop),
        behavior: "smooth",
      });
      scrollModeRef.current = "nearest";
    });

    return () => window.cancelAnimationFrame(frame);
  }, [selectedKey, revealedChapterKeys, clampedChapterPage]);

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

  function selectItem(item) {
    scrollModeRef.current = "nearest";
    setSelectedKey(recordKey(item));
  }

  function updateFilters(nextFilters, options = {}) {
    const nextSource = options.source !== undefined ? options.source : (
      reviewSource === "extraction_run"
      && nextFilters.bookId === filters.bookId
      && nextFilters.chapterRange === filters.chapterRange
        ? reviewSource
        : ""
    );

    setFilters(nextFilters);
    setSearchParams(filtersToSearchParams(nextFilters, nextSource), { replace: true });
  }

  function clearAllFilters() {
    updateFilters(DEFAULT_REVIEW_FILTERS, { source: "" });
  }

  function clearExtractionScope() {
    updateFilters({ ...filters, chapterRange: "" }, { source: "" });
  }

  function removeFilter(key) {
    const nextFilters = { ...filters };

    if (key === "bookId") {
      nextFilters.bookId = DEFAULT_REVIEW_FILTERS.bookId;
      nextFilters.chapterRange = "";
    } else if (key === "chapterRange") {
      nextFilters.chapterRange = "";
    } else if (key === "typeGroup") {
      nextFilters.typeGroup = DEFAULT_REVIEW_FILTERS.typeGroup;
    } else if (key === "status") {
      nextFilters.status = DEFAULT_REVIEW_FILTERS.status;
    } else if (key === "warningsOnly") {
      nextFilters.warningsOnly = DEFAULT_REVIEW_FILTERS.warningsOnly;
    } else if (key === "search") {
      nextFilters.search = DEFAULT_REVIEW_FILTERS.search;
    }

    updateFilters(nextFilters, { source: key === "chapterRange" || key === "bookId" ? "" : reviewSource });
  }

  function changeChapterPage(nextPage) {
    const normalizedPage = Math.min(Math.max(nextPage, 1), totalChapterPages);
    const nextGroups = groups.slice(
      (normalizedPage - 1) * CHAPTER_GROUP_PAGE_SIZE,
      normalizedPage * CHAPTER_GROUP_PAGE_SIZE
    );
    const nextItem = nextGroups.flatMap((group) => group.items)[0] || null;

    setChapterPage(normalizedPage);

    if (!nextItem) return;

    const nextGroupKey = chapterKeyForItem(nextItem);
    scrollModeRef.current = "nearest";
    setExpandedChapterKeys((current) => {
      if (current.has(nextGroupKey)) return current;
      const next = new Set(current);
      next.add(nextGroupKey);
      return next;
    });
    setSelectedKey(recordKey(nextItem));
  }

  function moveSelection(direction) {
    if (orderedItems.length === 0) return;

    const currentIndex = orderedItems.findIndex((item) => recordKey(item) === selectedKey);
    const nextIndex = currentIndex < 0
      ? 0
      : Math.min(Math.max(currentIndex + direction, 0), orderedItems.length - 1);
    const nextItem = orderedItems[nextIndex];
    const nextGroupKey = chapterKeyForItem(nextItem);
    const currentGroupKey = selectedGroupKey;

    scrollModeRef.current = nextGroupKey === currentGroupKey ? "nearest" : "center";
    setChapterPage(pageForReviewItem(groups, nextItem));
    setExpandedChapterKeys((current) => {
      if (current.has(nextGroupKey)) return current;
      const next = new Set(current);
      next.add(nextGroupKey);
      return next;
    });
    setSelectedKey(recordKey(nextItem));
  }

  function toggleChapter(groupKey) {
    setExpandedChapterKeys((current) => {
      const next = new Set(current);

      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }

      return next;
    });
  }

  function revealChapter(groupKey) {
    setRevealedChapterKeys((current) => {
      const next = new Set(current);
      next.add(groupKey);
      return next;
    });
  }

  async function updateReviewItem(item, reviewStatus) {
    const currentIndex = orderedItems.findIndex((orderedItem) => recordKey(orderedItem) === recordKey(item));
    const nextItem = currentIndex >= 0
      ? orderedItems[currentIndex + 1] || orderedItems[currentIndex - 1] || null
      : null;
    const statusFilterWillStillShowItem = filters.status === "all" || filters.status === reviewStatus;
    const nextSelectionKey = statusFilterWillStillShowItem
      ? recordKey(item)
      : nextItem
        ? recordKey(nextItem)
        : "";

    pendingSelectionKeyRef.current = nextSelectionKey;

    if (!statusFilterWillStillShowItem && nextItem) {
      const nextGroupKey = chapterKeyForItem(nextItem);
      const currentGroupKey = chapterKeyForItem(item);

      scrollModeRef.current = nextGroupKey === currentGroupKey ? "nearest" : "center";
      setExpandedChapterKeys((current) => {
        if (current.has(nextGroupKey)) return current;
        const next = new Set(current);
        next.add(nextGroupKey);
        return next;
      });
    } else if (statusFilterWillStillShowItem) {
      scrollModeRef.current = "nearest";
    }

    setIsSaving(true);

    try {
      await fetchJson(`${API_BASE_URL}/admin/review/${item.entityType}/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_status: reviewStatus,
          expected_review_version: item.review_version,
        }),
      });
      await onRefresh?.({ showLoading: false });
    } catch (err) {
      if (isReviewConflict(err)) {
        setReviewConflict({ message: reviewConflictMessage(err) });
        return;
      }

      throw err;
    } finally {
      setIsSaving(false);
    }
  }

  async function saveReviewProposalEdits(payload, options = {}) {
    if (!editingItem) return;

    setEditError("");
    setIsSaving(true);
    pendingSelectionKeyRef.current = recordKey(editingItem);
    const targetEntityType = options.targetEntityType;
    const isConversion = targetEntityType && targetEntityType !== editingItem.entityType;

    try {
      const requestPayload = {
        ...payload,
        expected_review_version: editingItem.review_version,
      };
      const savedItem = await fetchJson(`${API_BASE_URL}/admin/review/${editingItem.entityType}/${editingItem.id}${isConversion ? "/convert" : ""}`, {
        method: isConversion ? "POST" : "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isConversion ? { ...requestPayload, target_entity_type: targetEntityType } : requestPayload),
      });

      if (isConversion && savedItem?.entity_type && savedItem?.review_item?.id) {
        pendingSelectionKeyRef.current = `${savedItem.entity_type}:${savedItem.review_item.id}`;
      }

      await onRefresh?.({ showLoading: false });
      setEditingItem(null);
    } catch (err) {
      if (isReviewConflict(err)) {
        setReviewConflict({ message: reviewConflictMessage(err) });
        return;
      }

      setEditError(err.message || "Could not save proposal changes.");
    } finally {
      setIsSaving(false);
    }
  }

  async function refreshAfterReviewConflict() {
    setReviewConflict(null);
    setEditError("");
    setEditingItem(null);
    await onRefresh?.({ showLoading: false });
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
        </div>
      </header>

      <div className="workspace-page-body review-page-body">
        <div className="review-status-strip" aria-label="Review queue status summary">
          {summaryCards.map((card) => {
            const Icon = card.Icon;
            return (
              <span className={`review-status-pill ${card.color}`} key={card.label}>
                <Icon aria-hidden="true" size={14} strokeWidth={1.9} />
                <strong>{card.value}</strong>
                {card.label}
              </span>
            );
          })}
        </div>

        <ReviewFilters
          books={books}
          countsByBook={countsByBook}
          filters={filters}
          onChange={updateFilters}
          onClearFilters={clearAllFilters}
        />

        <ReviewActiveFilterStrip
          booksById={booksById}
          filters={filters}
          onClearAll={clearAllFilters}
          onClearExtractionScope={clearExtractionScope}
          onRemoveFilter={removeFilter}
          source={reviewSource}
        />

        <div className={selectedItem ? "review-workspace-grid review-focused" : "review-workspace-grid"}>
          <main className="review-feed-panel admin-panel">
            <div className="review-panel-title">
              <div>
                <h2>
                  {filters.bookId === "all"
                    ? "All Review Items"
                    : `Book ${booksById.get(Number(filters.bookId))?.number || filters.bookId}: ${booksById.get(Number(filters.bookId))?.title || ""}`}
                </h2>
                <span>
                  {filteredItems.length} shown
                  {filters.bookId !== "all" ? ` - ${countsByBook[Number(filters.bookId)] || 0} pending in this book` : ""}
                </span>
              </div>
            </div>

            <div className="review-feed-list" ref={feedListRef}>
              {groups.length === 0 ? (
                <div className="review-empty-feed">
                  <strong>No review items match the current filters.</strong>
                  <p>Try a different book, status, type, or search term.</p>
                </div>
              ) : (
                visibleGroups.map((group) => {
                  const groupKey = chapterGroupKey(group);

                  return (
                    <ReviewChapterGroup
                      key={groupKey}
                      group={group}
                      selectedKey={selectedKey}
                      onSelect={selectItem}
                      isExpanded={expandedChapterKeys.has(groupKey)}
                      isRevealed={revealedChapterKeys.has(groupKey)}
                      onToggle={() => toggleChapter(groupKey)}
                      onShowAll={() => revealChapter(groupKey)}
                      visibleLimit={CHAPTER_ITEM_PREVIEW_LIMIT}
                    />
                  );
                })
              )}
            </div>

            <footer className="review-feed-footer">
              <span>
                {groups.length === 0
                  ? "No chapters shown"
                  : `Showing chapters ${firstVisibleGroup?.chapter?.chapter_number || "-"}-${lastVisibleGroup?.chapter?.chapter_number || "-"} - ${filteredItems.length} pending items`}
              </span>
              <div>
                <button
                  type="button"
                  className="admin-secondary-button review-feed-page-button"
                  disabled={clampedChapterPage <= 1}
                  onClick={() => changeChapterPage(clampedChapterPage - 1)}
                >
                  Prev
                </button>
                <button type="button" className="admin-secondary-button review-feed-page-button" disabled>
                  {clampedChapterPage}
                </button>
                <button
                  type="button"
                  className="admin-secondary-button review-feed-page-button"
                  disabled={clampedChapterPage >= totalChapterPages}
                  onClick={() => changeChapterPage(clampedChapterPage + 1)}
                >
                  Next
                </button>
              </div>
            </footer>
          </main>

          <ReviewDetailPanel
            item={selectedItem}
            isSaving={isSaving}
            onApprove={(item) => updateReviewItem(item, "approved")}
            onReject={(item) => updateReviewItem(item, "rejected")}
            onNext={() => moveSelection(1)}
            onPrevious={() => moveSelection(-1)}
            onViewContext={setContextEvidence}
            onEdit={(item) => {
              setEditError("");
              setEditingItem(item);
            }}
            canGoNext={!isLastSelected}
            canGoPrevious={!isFirstSelected}
            emptyTitle={filteredItems.length === 0 ? "No pending review items" : "Select a review item"}
            emptyDescription={
              filteredItems.length === 0
                ? "There are no review items matching the current filters."
                : "Choose an extracted record from the queue to inspect evidence and moderate it."
            }
          />
        </div>
      </div>
      {contextEvidence ? (
        <ReviewContextModal
          evidence={contextEvidence}
          fallbackChapter={selectedChapter}
          onClose={() => setContextEvidence(null)}
        />
      ) : null}
      {editingItem ? (
        <ReviewEditProposalModal
          item={editingItem}
          isSaving={isSaving}
          error={editError}
          onClose={() => {
            if (!isSaving) {
              setEditError("");
              setEditingItem(null);
            }
          }}
          onSave={saveReviewProposalEdits}
          onViewContext={setContextEvidence}
        />
      ) : null}
      {reviewConflict ? (
        <AdminNoticeModal
          title="Review item changed"
          message={reviewConflict.message}
          actionLabel="Refresh Review Queue"
          onAction={refreshAfterReviewConflict}
          onClose={refreshAfterReviewConflict}
        />
      ) : null}
    </section>
  );
}
