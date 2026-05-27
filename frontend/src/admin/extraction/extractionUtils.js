export function runProgress(run) {
  return run?.total_chapters
    ? Math.round((run.completed_chapters / run.total_chapters) * 100)
    : 0;
}

export function statusTone(status) {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "processing") return "info";
  if (status === "queued") return "warning";
  if (status === "cancelled" || status === "skipped") return "warning";
  return "neutral";
}

export function runTitle(run) {
  if (!run) return "No extraction run";

  const bookLabel = run.book ? `Book ${run.book.number}` : "Novel";

  if (run.scope_type === "single_chapter") {
    return `${bookLabel}: Chapter ${run.chapter_start}`;
  }

  if (run.scope_type === "chapter_range") {
    return `${bookLabel}: Chapters ${run.chapter_start}-${run.chapter_end}`;
  }

  if (run.scope_type === "book") {
    return `${bookLabel}: Full Book Extraction`;
  }

  if (run.scope_type === "retry_failed") {
    const bookLabel = run.book ? `Book ${run.book.number}` : "Novel";
    return `${bookLabel}: Continue from Chapter ${run.chapter_start}`;
  }

  return "Full Novel Extraction";
}

export function formatRunDate(value) {
  return value ? new Date(value).toLocaleString() : "Not started";
}

export function extractionProgressFromRuns(runs, totalChapters) {
  const completedChapterIds = new Set();

  runs.forEach((run) => {
    (run.run_chapters || []).forEach((runChapter) => {
      if (runChapter.status === "completed") {
        completedChapterIds.add(runChapter.chapter_id);
      }
    });
  });

  const extractedChapterCount = completedChapterIds.size ||
    runs
      .filter((run) => run.status === "completed")
      .reduce((sum, run) => sum + (run.completed_chapters || 0), 0);
  const boundedExtracted = Math.min(extractedChapterCount, totalChapters || extractedChapterCount);
  const progress = totalChapters ? Math.round((boundedExtracted / totalChapters) * 100) : 0;

  return {
    extractedChapterCount,
    boundedExtracted,
    progress,
    pendingChapterCount: Math.max((totalChapters || 0) - boundedExtracted, 0),
  };
}
