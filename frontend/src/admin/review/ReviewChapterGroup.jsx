import React from "react";
import { ChevronDown, ChevronRight, TriangleAlert } from "lucide-react";
import { chapterLabel, cleanChapterTitle } from "../../utils/wikiFormat.js";
import ReviewItemCard from "./ReviewItemCard.jsx";
import { recordKey, reviewWarnings } from "./reviewUtils.js";

export default function ReviewChapterGroup({
  group,
  selectedKey,
  onSelect,
  isExpanded,
  isRevealed,
  onToggle,
  onShowAll,
  visibleLimit = 8,
}) {
  const warningCount = group.items.reduce((total, item) => total + reviewWarnings(item).length, 0);
  const visibleItems = isRevealed ? group.items : group.items.slice(0, visibleLimit);
  const hiddenItemCount = Math.max(group.items.length - visibleItems.length, 0);
  const Chevron = isExpanded ? ChevronDown : ChevronRight;

  return (
    <section className={isExpanded ? "review-chapter-group expanded" : "review-chapter-group"}>
      <button type="button" className="review-chapter-header" onClick={onToggle} aria-expanded={isExpanded}>
        <span className="review-chapter-chevron">
          <Chevron aria-hidden="true" size={16} strokeWidth={2.2} />
        </span>
        <div className="review-chapter-heading">
          <strong title={cleanChapterTitle(group.chapter)}>
            {chapterLabel(group.chapter)}
          </strong>
          <span>{group.bookTitle}</span>
        </div>
        <span className="review-chapter-counts">
          <b>{group.items.length} pending</b>
          {warningCount > 0 && (
            <em>
              <TriangleAlert aria-hidden="true" size={13} strokeWidth={2} />
              {warningCount} warning{warningCount === 1 ? "" : "s"}
            </em>
          )}
        </span>
      </button>

      {isExpanded && (
        <div className="review-item-list">
          {visibleItems.map((item) => (
            <ReviewItemCard
              key={recordKey(item)}
              item={item}
              isSelected={selectedKey === recordKey(item)}
              onSelect={onSelect}
            />
          ))}
          {hiddenItemCount > 0 && (
            <button type="button" className="review-show-all-button" onClick={onShowAll}>
              Show all {group.items.length} items
            </button>
          )}
        </div>
      )}
    </section>
  );
}
