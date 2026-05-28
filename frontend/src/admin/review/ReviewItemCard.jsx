import React from "react";
import {
  ClipboardList,
  ChevronRight,
  FileText,
  Package,
  Sparkles,
  TrendingUp,
  UserRound,
} from "lucide-react";
import {
  confidenceLevel,
  confidenceText,
  formatReviewType,
  recordKey,
  reviewTitle,
  reviewWarnings,
} from "./reviewUtils.js";

const iconMap = {
  characters: UserRound,
  character_metadata_proposals: FileText,
  progression_events: TrendingUp,
  skills: Sparkles,
  items: Package,
  character_skills: Sparkles,
  character_items: Package,
  life_events: TrendingUp,
  events: ClipboardList,
};

export default function ReviewItemCard({ item, isSelected, onSelect }) {
  const Icon = iconMap[item.entityType] || ClipboardList;
  const warnings = reviewWarnings(item);
  const level = confidenceLevel(item);

  return (
    <button
      type="button"
      className={isSelected ? "review-item-card active" : "review-item-card"}
      onClick={() => onSelect(item)}
    >
      <span className={`review-item-icon ${item.typeGroup}`}>
        <Icon aria-hidden="true" size={16} strokeWidth={1.9} />
      </span>
      <span className="review-item-main">
        <small>{formatReviewType(item.entityType)}</small>
        <strong title={reviewTitle(item)}>{reviewTitle(item)}</strong>
      </span>
      <span className={`review-status-badge ${item.review_status}`}>{item.review_status}</span>
      <span className={`review-confidence ${level}`}>
        <i />
        {warnings.length > 0 ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : confidenceText(item)}
      </span>
      <span className="review-row-arrow" aria-hidden="true">
        <ChevronRight size={15} strokeWidth={2} />
      </span>
      <span className="sr-only">{recordKey(item)}</span>
    </button>
  );
}
