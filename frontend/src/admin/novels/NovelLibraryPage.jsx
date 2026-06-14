import React from "react";
import { ArrowRight, BadgeCheck, ClipboardList, Database, Play, Plus, Search, TriangleAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";
import EmptyState from "../components/EmptyState.jsx";
import CreateNovelModal from "./CreateNovelModal.jsx";
import EditNovelModal from "./EditNovelModal.jsx";
import NovelCard from "./NovelCard.jsx";

function OperationStatCard({ action, detail, disabled, icon: Icon, label, onAction, tone, value }) {
  return (
    <article className={`library-op-card ${tone}`}>
      <div className="library-op-card-main">
        <span className="library-op-icon">
          <Icon aria-hidden="true" size={22} strokeWidth={1.8} />
        </span>
        <div>
          <strong>{value}</strong>
          <span>{label}</span>
          <small>{detail}</small>
        </div>
      </div>
      {action ? (
        <button className="library-op-link" disabled={disabled} type="button" onClick={onAction}>
          {action}
          <ArrowRight aria-hidden="true" size={14} strokeWidth={1.9} />
        </button>
      ) : null}
    </article>
  );
}

export default function NovelLibraryPage({ canCreateNovel = true, novels, loading, onCreateNovel, onOpenNovel, onUpdateNovel }) {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = React.useState("");
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [editingNovel, setEditingNovel] = React.useState(null);

  const filteredNovels = novels.filter((novel) =>
    `${novel.title} ${novel.author || ""}`.toLowerCase().includes(searchTerm.trim().toLowerCase())
  );
  const totalPending = novels.reduce((sum, novel) => sum + (novel.pending_review_count || 0), 0);
  const totalWarnings = novels.reduce((sum, novel) => sum + (novel.warning_count || 0), 0);
  const activeExtractions = novels.reduce((sum, novel) => sum + (novel.active_extraction_count || 0), 0);
  const completedToday = novels.reduce((sum, novel) => sum + (novel.completed_today_count || 0), 0);
  const approvedRecords = novels.reduce((sum, novel) => sum + (novel.approved_record_count || 0), 0);

  async function handleCreate(payload) {
    const createdNovel = await onCreateNovel(payload);
    setIsCreateOpen(false);

    if (createdNovel) {
      onOpenNovel(createdNovel);
    }
  }

  async function handleUpdate(novelId, payload) {
    const updatedNovel = await onUpdateNovel(novelId, payload);

    if (updatedNovel) {
      setEditingNovel(null);
    }
  }

  return (
    <>
      <div className="admin-page-header library-page-header">
        <div>
          <h1>Novel Library</h1>
          <p>Editorial workspace for AI extraction, review coverage, and wiki publishing.</p>
        </div>
        <div className="admin-header-actions">
          <div className="library-search-field" role="search">
            <Search aria-hidden="true" size={17} strokeWidth={1.8} />
            <input
              aria-label="Search novels"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search novels..."
            />
          </div>
          {canCreateNovel ? (
            <button type="button" onClick={() => setIsCreateOpen(true)}>
              <Plus aria-hidden="true" size={17} strokeWidth={1.9} />
              Create Novel
            </button>
          ) : null}
        </div>
      </div>

      <section className="library-op-grid">
        <OperationStatCard
          action="View Review Queue"
          detail="Items waiting for review"
          icon={ClipboardList}
          label="Pending Reviews"
          tone="purple"
          value={totalPending}
        />
        <OperationStatCard
          action="View Warnings"
          detail="Need editorial attention"
          icon={TriangleAlert}
          label="Warnings"
          tone="orange"
          value={totalWarnings}
        />
        <OperationStatCard
          action="Go to Extraction"
          detail="Currently running"
          disabled={!novels.length}
          icon={Play}
          label="Active Extraction"
          onAction={() => {
            const targetNovel = novels.find((novel) => novel.active_extraction_count > 0) || novels[0];
            if (targetNovel) {
              navigate(`/admin/novels/${targetNovel.id}/extraction`);
            }
          }}
          tone="green"
          value={activeExtractions}
        />
        <OperationStatCard
          action="View Extraction Runs"
          detail="Extraction runs completed"
          icon={BadgeCheck}
          label="Completed Today"
          tone="blue"
          value={completedToday}
        />
        <OperationStatCard
          action="View Wiki Data"
          detail="Published to wiki"
          icon={Database}
          label="Approved Records"
          tone="cyan"
          value={approvedRecords}
        />
      </section>

      <section className="admin-panel library-novel-panel">
        <div className="admin-section-header library-section-header">
          <div>
            <h2>Your Novels</h2>
            <p>{loading ? "Loading workspace records..." : `${filteredNovels.length} of ${novels.length} novels shown`}</p>
          </div>
          <span>Recently Updated</span>
        </div>

        {filteredNovels.length === 0 ? (
          <EmptyState
            title={novels.length === 0 ? "No novels yet" : "No matching novels"}
            message={
              novels.length === 0
                ? "Create a novel workspace, then upload books inside it."
                : "Try a different search term."
            }
          />
        ) : (
          <div className="admin-novel-list">
            <div className="library-novel-head">
              <span>Novel</span>
              <span>Review Coverage</span>
              <span>Approved</span>
              <span>Pending</span>
              <span>Warnings</span>
              <span>Last Activity</span>
              <span>Actions</span>
            </div>
            {filteredNovels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} onEdit={setEditingNovel} onOpen={onOpenNovel} />
            ))}
          </div>
        )}
      </section>

      {isCreateOpen ? (
        <CreateNovelModal onClose={() => setIsCreateOpen(false)} onCreate={handleCreate} />
      ) : null}

      {editingNovel ? (
        <EditNovelModal
          novel={editingNovel}
          onClose={() => setEditingNovel(null)}
          onSave={handleUpdate}
        />
      ) : null}
    </>
  );
}
