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

const ORDINAL_WORDS = {
  first: "1st",
  second: "2nd",
  third: "3rd",
  fourth: "4th",
  fifth: "5th",
  sixth: "6th",
  seventh: "7th",
  eighth: "8th",
  ninth: "9th",
  tenth: "10th",
  eleventh: "11th",
  twelfth: "12th",
  thirteenth: "13th",
  fourteenth: "14th",
  fifteenth: "15th",
  sixteenth: "16th",
  seventeenth: "17th",
  eighteenth: "18th",
  nineteenth: "19th",
  twentieth: "20th",
};

const LOWERCASE_CULTIVATION_WORDS = new Set(["a", "an", "and", "at", "by", "for", "from", "in", "of", "the", "to"]);

function titleCaseCultivationText(value) {
  return value
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((word, index) => {
      const lower = word.toLowerCase();

      if (ORDINAL_WORDS[lower]) {
        return ORDINAL_WORDS[lower];
      }

      if (/^\d+(st|nd|rd|th)$/i.test(word)) {
        return lower;
      }

      if (index > 0 && LOWERCASE_CULTIVATION_WORDS.has(lower)) {
        return lower;
      }

      return `${lower.charAt(0).toUpperCase()}${lower.slice(1)}`;
    })
    .join(" ");
}

export function formatCultivationValue(value) {
  if (!value) {
    return "";
  }

  return titleCaseCultivationText(value);
}

export function splitCultivationValue(value) {
  const formatted = formatCultivationValue(value);

  if (!formatted) {
    return { realm: "Unknown", stage: "Unknown" };
  }

  const separator = formatted.toLowerCase().lastIndexOf(" of ");

  if (separator === -1) {
    return { realm: formatted, stage: "Known" };
  }

  return {
    realm: formatted.slice(separator + 4).trim(),
    stage: formatted.slice(0, separator).trim(),
  };
}

export function cultivationRealmKey(value) {
  return splitCultivationValue(value).realm.toLowerCase();
}
