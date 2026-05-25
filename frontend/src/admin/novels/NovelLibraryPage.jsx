import React from "react";
import EmptyState from "../components/EmptyState.jsx";
import StatCard from "../components/StatCard.jsx";
import CreateNovelModal from "./CreateNovelModal.jsx";
import NovelCard from "./NovelCard.jsx";

export default function NovelLibraryPage({ novels, loading, onCreateNovel, onOpenNovel }) {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);

  const filteredNovels = novels.filter((novel) =>
    novel.title.toLowerCase().includes(searchTerm.trim().toLowerCase())
  );
  const totalBooks = novels.reduce((sum, novel) => sum + (novel.book_count || 0), 0);
  const totalChapters = novels.reduce((sum, novel) => sum + (novel.chapter_count || 0), 0);
  const totalPending = novels.reduce((sum, novel) => sum + (novel.pending_review_count || 0), 0);
  const totalWarnings = novels.reduce((sum, novel) => sum + (novel.warning_count || 0), 0);

  async function handleCreate(payload) {
    const createdNovel = await onCreateNovel(payload);
    setIsCreateOpen(false);

    if (createdNovel) {
      onOpenNovel(createdNovel);
    }
  }

  return (
    <>
      <div className="admin-page-header">
        <div>
          <h1>Novel Library</h1>
          <p>Manage all novels in your library.</p>
        </div>
        <div className="admin-header-actions">
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search novels..."
          />
          <button type="button" onClick={() => setIsCreateOpen(true)}>
            Create Novel
          </button>
        </div>
      </div>

      <section className="admin-stat-grid">
        <StatCard label="Total Novels" value={novels.length} detail="In library" tone="purple" />
        <StatCard label="Total Books" value={totalBooks} detail="Across all novels" tone="blue" />
        <StatCard label="Total Chapters" value={totalChapters} detail="Across all novels" tone="green" />
        <StatCard label="Pending Reviews" value={totalPending} detail="Across all novels" tone="orange" />
        <StatCard label="Warnings" value={totalWarnings} detail="Need attention" tone="red" />
      </section>

      <section className="admin-panel">
        <div className="admin-section-header">
          <h2>Novels</h2>
          <span>{loading ? "Loading..." : `${filteredNovels.length} shown`}</span>
        </div>

        {filteredNovels.length === 0 ? (
          <EmptyState
            title={novels.length === 0 ? "No novels yet" : "No matching novels"}
            message={
              novels.length === 0
                ? "Create a novel workspace, then upload books inside it."
                : "Try a different search term."
            }
            action={
              novels.length === 0 ? (
                <button type="button" onClick={() => setIsCreateOpen(true)}>
                  Create Novel
                </button>
              ) : null
            }
          />
        ) : (
          <div className="admin-novel-list">
            {filteredNovels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} onOpen={onOpenNovel} />
            ))}
          </div>
        )}
      </section>

      {isCreateOpen ? (
        <CreateNovelModal onClose={() => setIsCreateOpen(false)} onCreate={handleCreate} />
      ) : null}
    </>
  );
}
