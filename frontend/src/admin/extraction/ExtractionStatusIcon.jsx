import React from "react";
import { CheckCircle2, Clock3, LoaderCircle, SkipForward, TriangleAlert } from "lucide-react";

const STATUS_ICONS = {
  pending: Clock3,
  processing: LoaderCircle,
  running: LoaderCircle,
  queued: Clock3,
  completed: CheckCircle2,
  failed: TriangleAlert,
  skipped: SkipForward,
  cancelled: SkipForward,
};

export default function ExtractionStatusIcon({ className = "", status }) {
  const Icon = STATUS_ICONS[status] || Clock3;
  const isSpinning = status === "processing" || status === "running";
  const statusLabel = status ? status.replace(/_/g, " ") : "unknown";

  return (
    <span
      className={`extraction-status-icon ${status || "unknown"} ${className}`}
      title={statusLabel}
      aria-label={statusLabel}
    >
      <Icon
        aria-hidden="true"
        className={isSpinning ? "animate-spin" : ""}
        size={17}
        strokeWidth={1.9}
      />
    </span>
  );
}
