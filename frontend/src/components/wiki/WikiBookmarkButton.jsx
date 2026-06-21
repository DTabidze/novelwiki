import React from "react";
import { Bookmark } from "lucide-react";

export default function WikiBookmarkButton({ entity, entityType, onToggle }) {
  const bookmarked = Boolean(entity?.is_bookmarked);

  function handleClick(event) {
    event.preventDefault();
    event.stopPropagation();
    onToggle?.(entityType, entity);
  }

  return (
    <button
      aria-label={bookmarked ? "Remove bookmark" : "Add bookmark"}
      aria-pressed={bookmarked}
      className={bookmarked ? "wiki-bookmark-toggle active" : "wiki-bookmark-toggle"}
      title={bookmarked ? "Remove bookmark" : "Add bookmark"}
      type="button"
      onClick={handleClick}
    >
      <Bookmark aria-hidden="true" size={18} strokeWidth={2.2} />
    </button>
  );
}
