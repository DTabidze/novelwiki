export function firstDescriptionChunk(description) {
  if (!description) {
    return "";
  }

  return description.split(/\n\s*\n/)[0].trim();
}

export function initialsForName(name) {
  return (name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function chapterLabel(chapter) {
  return chapter ? `Chapter ${chapter.chapter_number}` : "Unknown chapter";
}

export function relationshipLabel(relationship) {
  const type = relationship.relationship_type
    ? relationship.relationship_type.replace("_", " ")
    : "known";
  const chapter = relationship.chapter ? ` in Chapter ${relationship.chapter.chapter_number}` : "";
  return `${type.charAt(0).toUpperCase()}${type.slice(1)}${chapter}`;
}

export function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

export function formatDate(value) {
  if (!value) {
    return "Unknown";
  }

  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
