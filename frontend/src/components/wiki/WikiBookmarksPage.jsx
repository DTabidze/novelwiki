import React from "react";
import { BookOpen, Bookmark, Layers3, Library, Package, Sparkles, Users } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { listWikiBookmarks } from "../../api.js";
import { formatCultivationValue, formatNumber, initialsForName, skillCategoryClass } from "../../utils/wikiFormat.js";
import { ItemTypeIcon, itemTypeFor, itemTypeLabel } from "./WikiItemTypes.jsx";
import WikiAvatar from "./WikiAvatar.jsx";
import WikiBookmarkButton from "./WikiBookmarkButton.jsx";

const BOOKMARK_TABS = [
  { id: "all", label: "All", Icon: Layers3 },
  { id: "novel", label: "Novels", Icon: Library },
  { id: "character", label: "Characters", Icon: Users },
  { id: "skill", label: "Skills", Icon: Sparkles },
  { id: "item", label: "Items", Icon: Package },
];

const VALID_TABS = new Set(BOOKMARK_TABS.map((tab) => tab.id));

function isUnknown(value) {
  return !value || /^unknown/i.test(String(value).trim());
}

function bookmarkNovelTitle(bookmark) {
  return bookmark.novel?.title || bookmark.entity?.title || "Unknown novel";
}

function characterAffiliation(character) {
  const parts = [character.current_position, character.faction_or_affiliation || character.origin]
    .map((value) => String(value || "").trim())
    .filter((value) => value && !isUnknown(value));

  return [...new Set(parts)].join(" · ");
}

function cleanPreview(value, fallback) {
  return (value || fallback).replace(/\s+/g, " ");
}

function BookmarkRow({ bookmark, onOpen, onRemove }) {
  const entity = bookmark.entity;

  if (!entity) {
    return null;
  }

  if (bookmark.entity_type === "novel") {
    const coverage = entity.wiki_coverage_end_chapter || 0;
    const totalChapters = entity.chapter_count || 0;

    return (
      <button className="wiki-bookmark-row novel" type="button" onClick={() => onOpen(bookmark)}>
        <WikiAvatar name={entity.title} size="small" />
        <span className="wiki-bookmark-main">
          <strong>{entity.title}</strong>
          <small>{entity.author || "Unknown author"}</small>
        </span>
        <span className="wiki-bookmark-meta">
          <small>Wiki Coverage</small>
          <strong>{formatNumber(coverage)} / {formatNumber(totalChapters)} chapters</strong>
        </span>
        <WikiBookmarkButton entity={entity} entityType="novel" onToggle={() => onRemove(bookmark)} />
      </button>
    );
  }

  if (bookmark.entity_type === "character") {
    const cultivation = formatCultivationValue(entity.current_cultivation_level);
    const subtitle = characterAffiliation(entity) || bookmarkNovelTitle(bookmark);

    return (
      <button className="wiki-bookmark-row" type="button" onClick={() => onOpen(bookmark)}>
        <span className={`wiki-character-initials tone-${entity.id % 6}`}>{initialsForName(entity.name)}</span>
        <span className="wiki-bookmark-main">
          <span>
            <strong>{entity.name}</strong>
            {cultivation ? <em className="wiki-cultivation-badge">{cultivation}</em> : null}
          </span>
          <small>{subtitle}</small>
        </span>
        <span className="wiki-bookmark-meta">
          <small>Novel</small>
          <strong>{bookmarkNovelTitle(bookmark)}</strong>
        </span>
        <WikiBookmarkButton entity={entity} entityType="character" onToggle={() => onRemove(bookmark)} />
      </button>
    );
  }

  if (bookmark.entity_type === "skill") {
    const description = cleanPreview(entity.description, "No description recorded yet.");

    return (
      <button className="wiki-bookmark-row" type="button" onClick={() => onOpen(bookmark)}>
        <span className="wiki-skill-icon small">S</span>
        <span className="wiki-bookmark-main">
          <span>
            <strong>{entity.name}</strong>
            <small className={`wiki-type-badge skill ${skillCategoryClass(entity.category)}`}>
              {entity.category || "Skill"}
            </small>
          </span>
          <small>{description}</small>
        </span>
        <span className="wiki-bookmark-meta">
          <small>Novel</small>
          <strong>{bookmarkNovelTitle(bookmark)}</strong>
        </span>
        <WikiBookmarkButton entity={entity} entityType="skill" onToggle={() => onRemove(bookmark)} />
      </button>
    );
  }

  if (bookmark.entity_type === "item") {
    const itemType = itemTypeFor(entity);
    const description = cleanPreview(entity.description, "No description recorded yet.");

    return (
      <button className="wiki-bookmark-row" type="button" onClick={() => onOpen(bookmark)}>
        <span className={`wiki-item-type-icon ${itemType}`}>
          <ItemTypeIcon type={itemType} />
        </span>
        <span className="wiki-bookmark-main">
          <span>
            <strong>{entity.name}</strong>
            <small className={`wiki-type-badge ${itemType}`}>{itemTypeLabel(itemType).toUpperCase()}</small>
          </span>
          <small>{description}</small>
        </span>
        <span className="wiki-bookmark-meta">
          <small>Novel</small>
          <strong>{bookmarkNovelTitle(bookmark)}</strong>
        </span>
        <WikiBookmarkButton entity={entity} entityType="item" onToggle={() => onRemove(bookmark)} />
      </button>
    );
  }

  return null;
}

function BookmarkGroup({ bookmarks, label, onOpen, onRemove }) {
  return (
    <section className="wiki-search-result-group">
      <header>
        <h2>{label}</h2>
        <span>{formatNumber(bookmarks.length)}</span>
      </header>
      {bookmarks.length ? (
        <div className="wiki-search-result-list">
          {bookmarks.map((bookmark) => (
            <BookmarkRow
              bookmark={bookmark}
              key={`${bookmark.entity_type}-${bookmark.entity_id}`}
              onOpen={onOpen}
              onRemove={onRemove}
            />
          ))}
        </div>
      ) : (
        <p className="wiki-muted-copy">No saved {label.toLowerCase()}.</p>
      )}
    </section>
  );
}

export default function WikiBookmarksPage({ onRemoveBookmark }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [bookmarks, setBookmarks] = React.useState([]);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const requestedType = searchParams.get("type") || "all";
  const activeType = VALID_TABS.has(requestedType) ? requestedType : "all";

  React.useEffect(() => {
    let active = true;

    setLoading(true);
    listWikiBookmarks()
      .then((rows) => {
        if (!active) return;
        setBookmarks((rows || []).filter((bookmark) => bookmark.entity));
        setError("");
      })
      .catch((requestError) => {
        if (!active) return;
        setError(requestError.status === 401 ? "Log in to view your bookmarks." : requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const groupedBookmarks = React.useMemo(() => ({
    novel: bookmarks.filter((bookmark) => bookmark.entity_type === "novel"),
    character: bookmarks.filter((bookmark) => bookmark.entity_type === "character"),
    skill: bookmarks.filter((bookmark) => bookmark.entity_type === "skill"),
    item: bookmarks.filter((bookmark) => bookmark.entity_type === "item"),
  }), [bookmarks]);

  const totalCount = bookmarks.length;
  const visibleTypes = activeType === "all"
    ? ["novel", "character", "skill", "item"].filter((type) => groupedBookmarks[type]?.length)
    : [activeType];

  function updateType(type) {
    const next = new URLSearchParams(searchParams);
    if (type === "all") {
      next.delete("type");
    } else {
      next.set("type", type);
    }
    setSearchParams(next, { replace: false });
  }

  function openBookmark(bookmark) {
    const entity = bookmark.entity;
    const novelId = bookmark.novel_id;

    if (bookmark.entity_type === "novel") navigate(`/wiki/novels/${entity.id}`);
    if (bookmark.entity_type === "character") navigate(`/wiki/novels/${novelId}/characters/${entity.id}`);
    if (bookmark.entity_type === "skill") navigate(`/wiki/novels/${novelId}/skills/${entity.id}`);
    if (bookmark.entity_type === "item") navigate(`/wiki/novels/${novelId}/items/${entity.id}`);
  }

  async function removeBookmark(bookmark) {
    setBookmarks((current) => current.filter((row) => row.id !== bookmark.id));

    try {
      await onRemoveBookmark?.(bookmark.entity_type, bookmark.entity);
    } catch {
      setBookmarks((current) => [bookmark, ...current]);
    }
  }

  return (
    <article className="wiki-search-results-page wiki-bookmarks-page">
      <header className="wiki-search-results-header">
        <div>
          <h1>Bookmarks</h1>
          <p>{formatNumber(totalCount)} saved wiki {totalCount === 1 ? "page" : "pages"}</p>
        </div>
      </header>

      <nav className="wiki-search-results-tabs" aria-label="Bookmark types">
        {BOOKMARK_TABS.map(({ Icon, id, label }) => (
          <button
            className={activeType === id ? "active" : ""}
            key={id}
            type="button"
            onClick={() => updateType(id)}
          >
            <Icon aria-hidden="true" size={16} />
            {label}
            <span>{id === "all" ? formatNumber(totalCount) : formatNumber(groupedBookmarks[id]?.length || 0)}</span>
          </button>
        ))}
      </nav>

      {loading ? <p className="wiki-loading">Loading bookmarks...</p> : null}

      {!loading && error ? (
        <section className="wiki-search-results-empty">
          <Bookmark aria-hidden="true" size={24} />
          <strong>{error}</strong>
          <p>Your saved novels, characters, skills, and items will appear here.</p>
        </section>
      ) : null}

      {!loading && !error && visibleTypes.length ? (
        <div className="wiki-search-result-groups">
          {visibleTypes.map((type) => {
            const tab = BOOKMARK_TABS.find((item) => item.id === type);
            return (
              <BookmarkGroup
                bookmarks={groupedBookmarks[type] || []}
                key={type}
                label={tab?.label || type}
                onOpen={openBookmark}
                onRemove={removeBookmark}
              />
            );
          })}
        </div>
      ) : null}

      {!loading && !error && !visibleTypes.length ? (
        <section className="wiki-search-results-empty">
          <BookOpen aria-hidden="true" size={24} />
          <strong>No bookmarks yet</strong>
          <p>Save novels, characters, skills, or items to build your personal wiki library.</p>
        </section>
      ) : null}
    </article>
  );
}
