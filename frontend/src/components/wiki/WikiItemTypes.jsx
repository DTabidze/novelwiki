import React from "react";

export const ITEM_TYPES = [
  { key: "all", label: "All Types" },
  { key: "weapon", label: "Weapons" },
  { key: "artifact", label: "Artifacts" },
  { key: "pill", label: "Pills" },
  { key: "manual", label: "Manuals" },
  { key: "material", label: "Materials" },
  { key: "miscellaneous", label: "Miscellaneous" },
];

export function itemTypeFor(item) {
  const searchable = `${item.category || ""} ${item.name || ""}`.toLowerCase();

  if (/(weapon|sword|blade|spear|bow|dagger)/.test(searchable)) {
    return "weapon";
  }

  if (/(artifact|treasure|mirror|gourd|pendant|bag of holding)/.test(searchable)) {
    return "artifact";
  }

  if (/(pill|medicine|elixir|pellet)/.test(searchable)) {
    return "pill";
  }

  if (/(manual|book|scroll|jade slip|slip)/.test(searchable)) {
    return "manual";
  }

  if (/(material|essence|core|stone|crystal|ore)/.test(searchable)) {
    return "material";
  }

  return "miscellaneous";
}

export function itemTypeLabel(type) {
  return ITEM_TYPES.find((itemType) => itemType.key === type)?.label.replace(/s$/, "") || "Miscellaneous";
}

export function ItemTypeIcon({ type }) {
  const iconProps = {
    "aria-hidden": "true",
    fill: "none",
    height: "20",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: "2",
    viewBox: "0 0 24 24",
    width: "20",
  };
  const paths = {
    weapon: (
      <>
        <polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5" />
        <line x1="13" x2="19" y1="19" y2="13" />
        <line x1="16" x2="20" y1="16" y2="20" />
        <line x1="19" x2="21" y1="21" y2="19" />
      </>
    ),
    artifact: (
      <>
        <path d="M6 3h12l4 6-10 13L2 9Z" />
        <path d="M11 3 8 9l4 13 4-13-3-6" />
        <path d="M2 9h20" />
      </>
    ),
    pill: (
      <>
        <path d="M10 2v7.31" />
        <path d="M14 9.3V2" />
        <path d="M8.5 2h7" />
        <path d="M14 9.3a6.5 6.5 0 1 1-4 0" />
        <path d="M5.52 16h12.96" />
      </>
    ),
    manual: (
      <>
        <path d="M15 12h-5" />
        <path d="M15 8h-5" />
        <path d="M19 17V5a2 2 0 0 0-2-2H4" />
        <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
      </>
    ),
    material: (
      <>
        <path d="M8.5 14.5A4 4 0 0 0 12 21a6 6 0 0 0 6-6c0-4-3-6-3-10-2 2-7 4-6.5 9.5Z" />
        <path d="M12 21c0-3 1.5-5 4-7" />
      </>
    ),
    miscellaneous: (
      <>
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
        <path d="M3.3 7 12 12l8.7-5" />
        <path d="M12 22V12" />
      </>
    ),
  };

  return <svg {...iconProps}>{paths[type] || paths.miscellaneous}</svg>;
}
