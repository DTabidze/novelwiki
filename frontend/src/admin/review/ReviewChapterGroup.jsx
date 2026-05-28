import React from "react";
import ReviewItemCard from "./ReviewItemCard.jsx";
import { recordKey } from "./reviewUtils.js";

export default function ReviewChapterGroup({ group, selectedKey, onSelect }) {
  return (
    <section className="review-chapter-group">
      <div className="review-chapter-header">
        <div>
          <strong>
            Chapter {group.chapter?.chapter_number || "-"} - {group.chapter?.title || "Unlinked source"}
          </strong>
          <span>{group.bookTitle}</span>
        </div>
        <small>{group.items.length}</small>
      </div>

      <div className="review-item-list">
        {group.items.map((item) => (
          <ReviewItemCard
            key={recordKey(item)}
            item={item}
            isSelected={selectedKey === recordKey(item)}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
