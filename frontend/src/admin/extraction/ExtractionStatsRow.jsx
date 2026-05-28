import React from "react";
import { BookOpen, CheckCircle2, Clock3, Files, TriangleAlert } from "lucide-react";
import StatCard from "../components/StatCard.jsx";

export default function ExtractionStatsRow({
  bookCount,
  chapterCount,
  failedRuns,
  progress,
  queuedRuns,
  extractedChapterCount,
}) {
  return (
    <section className="admin-stat-grid workspace-stats extraction-stats-row">
      <div className="extraction-stat-span-2">
        <StatCard icon={BookOpen} label="Books" value={bookCount} detail="Uploaded" tone="blue" />
      </div>
      <div className="extraction-stat-span-2">
        <StatCard icon={Files} label="Chapters" value={chapterCount} detail="Total chapters" tone="green" />
      </div>
      <div className="extraction-stat-span-3">
        <StatCard
          icon={CheckCircle2}
          label="Extracted"
          value={`${progress}%`}
          detail={`${extractedChapterCount} processed`}
          tone="purple"
        />
      </div>
      <div className="extraction-stat-span-2">
        <StatCard icon={Clock3} label="Queued" value={queuedRuns} detail="Runs" tone="orange" />
      </div>
      <div className="extraction-stat-span-3">
        <StatCard icon={TriangleAlert} label="Failed" value={failedRuns} detail="Runs" tone="red" />
      </div>
    </section>
  );
}
