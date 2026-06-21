import React from "react";
import { Search } from "lucide-react";
import WikiNovelCard from "./WikiNovelCard.jsx";
import { formatNumber } from "../../utils/wikiFormat.js";

export default function WikiLandingPage({ novels, onLoadNovel, onToggleBookmark }) {
  const [query, setQuery] = React.useState("");

  const visibleNovels = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return novels
      .filter((novel) => {
        if (!normalizedQuery) return true;

        return [novel.title, novel.author]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedQuery));
      })
      .sort((left, right) => {
        return new Date(right.last_wiki_updated_at || right.updated_at || 0) - new Date(left.last_wiki_updated_at || left.updated_at || 0);
      });
  }, [novels, query]);

  return (
    <article className="wiki-landing-page wiki-novel-library">
      <section className="wiki-library-header">
        <h1>Novels</h1>
        <p>Browse reader-ready wiki coverage for cultivation novels.</p>
      </section>

      <section className="wiki-library-toolbar">
        <label className="wiki-local-search-field">
          <Search aria-hidden="true" size={18} />
          <input type="search" placeholder="Search novel or author..." value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <span>{formatNumber(visibleNovels.length)} novels</span>
      </section>

      <section className="wiki-novel-grid" aria-label="Novel library">
        {visibleNovels.length === 0 ? (
          <div className="wiki-card wiki-library-empty">
            <strong>No novels found.</strong>
            <p>Try adjusting the search or filters.</p>
          </div>
        ) : null}
        {visibleNovels.map((wikiNovel) => (
          <WikiNovelCard
            key={wikiNovel.id}
            novel={wikiNovel}
            onOpen={onLoadNovel}
            onToggleBookmark={onToggleBookmark}
          />
        ))}
      </section>
    </article>
  );
}
