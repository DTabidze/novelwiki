import React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Calendar,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  FileClock,
  Filter,
  FilterX,
  Info,
  ListChecks,
  Pencil,
  Plus,
  Search,
  Trash2,
  UserRound,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";

const ENTITY_OPTIONS = [
  { value: "all", label: "All" },
  { value: "character", label: "Characters" },
  { value: "skill", label: "Skills" },
  { value: "item", label: "Items" },
  { value: "alias", label: "Character Aliases" },
  { value: "skill_alias", label: "Skill Aliases" },
  { value: "cultivation", label: "Cultivation" },
  { value: "character_skill", label: "Character Skills" },
  { value: "character_item", label: "Character Items" },
];

const CHANGE_OPTIONS = [
  { value: "all", label: "All" },
  { value: "updated", label: "Updated" },
  { value: "added", label: "Added" },
  { value: "removed", label: "Removed" },
];

const DATE_OPTIONS = [
  { value: "all", label: "All dates" },
  { value: "today", label: "Today" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
];

const PER_PAGE_OPTIONS = [10, 25, 50];

const CONTEXTUAL_ENTITY_TYPES = new Set([
  "alias",
  "skill_alias",
  "cultivation",
  "character_skill",
  "character_item",
]);

function changeIcon(changeType) {
  if (changeType === "added") return Plus;
  if (changeType === "removed" || changeType === "deleted") return Trash2;
  return Pencil;
}

function formatDate(value, options = {}) {
  if (!value) return "";

  return new Intl.DateTimeFormat(undefined, options).format(new Date(value));
}

function dayLabel(value) {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const sameDay = (first, second) =>
    first.getFullYear() === second.getFullYear()
    && first.getMonth() === second.getMonth()
    && first.getDate() === second.getDate();

  const fullDate = formatDate(value, { month: "long", day: "numeric", year: "numeric" });

  if (sameDay(date, today)) return `Today - ${fullDate}`;
  if (sameDay(date, yesterday)) return `Yesterday - ${fullDate}`;

  return fullDate;
}

function valueText(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") {
    if (value.chapter_number && value.title) {
      return `Chapter ${value.chapter_number} - ${value.title}`;
    }

    return JSON.stringify(value);
  }

  return String(value);
}

function shortText(value, maxLength = 78) {
  const text = valueText(value).replace(/\s+/g, " ").trim();

  if (text.length <= maxLength) return text;

  return `${text.slice(0, maxLength - 3).trim()}...`;
}

function contextualChangeText(log) {
  if (!["added", "removed"].includes(log.change_type)) return "";

  if (log.parent_entity_label) {
    return `${log.change_type === "added" ? "Added to" : "Removed from"} ${log.parent_entity_label}`;
  }

  const match = String(log.summary || "").match(/\b(to|from)\s+(.+?)\.?$/i);
  if (!match) return log.summary || "";

  const direction = match[1].toLowerCase();
  const target = match[2];
  const action = log.change_type === "added" ? "Added" : "Removed";

  return `${action} ${direction} ${target}`;
}

function rowEntityLabel(log) {
  if (log.parent_entity_label && CONTEXTUAL_ENTITY_TYPES.has(log.entity_type)) {
    return log.parent_entity_label;
  }

  return log.entity_label;
}

function changedRecordLabel(log) {
  const contextLabel = rowEntityLabel(log);

  if (!log.entity_label || log.entity_label === contextLabel) return "";

  return log.entity_label;
}

function dateRangeParams(range) {
  const now = new Date();

  if (range === "today") {
    return { date_from: now.toISOString().slice(0, 10), date_to: now.toISOString().slice(0, 10) };
  }

  if (range === "7d" || range === "30d") {
    const days = range === "7d" ? 7 : 30;
    const fromDate = new Date(now);
    fromDate.setDate(now.getDate() - days + 1);
    return { date_from: fromDate.toISOString().slice(0, 10), date_to: now.toISOString().slice(0, 10) };
  }

  return {};
}

function groupLogs(logs) {
  return logs.reduce((groups, log) => {
    const label = dayLabel(log.created_at);
    const group = groups.find((item) => item.label === label);

    if (group) {
      group.logs.push(log);
    } else {
      groups.push({ label, logs: [log] });
    }

    return groups;
  }, []);
}

function pageWindow(currentPage, totalPages) {
  const pages = [];
  const start = Math.max(1, Math.min(currentPage - 1, totalPages - 2));
  const end = Math.min(totalPages, start + 2);

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  return pages;
}

function publicPathForLog(log, novel) {
  const novelPath = `/wiki/novels/${novel?.id || log.novel_id}`;

  if (log.entity_type === "character") return `${novelPath}/characters/${log.entity_id}`;
  if (log.entity_type === "skill") return `${novelPath}/skills/${log.entity_id}`;
  if (log.entity_type === "item") return `${novelPath}/items/${log.entity_id}`;

  if (log.parent_entity_type === "character") return `${novelPath}/characters/${log.parent_entity_id}`;
  if (log.parent_entity_type === "skill") return `${novelPath}/skills/${log.parent_entity_id}`;
  if (log.parent_entity_type === "item") return `${novelPath}/items/${log.parent_entity_id}`;

  return novelPath;
}

function editorPathForLog(log, novelId) {
  const basePath = `/admin/novels/${novelId}/editor`;

  if (log.entity_type === "character") return `${basePath}?entity=characters&section=basic&character=${log.entity_id}`;
  if (log.entity_type === "skill") return `${basePath}?entity=skills&section=basic&skill=${log.entity_id}`;
  if (log.entity_type === "item") return `${basePath}?entity=items&section=basic&item=${log.entity_id}`;

  if (log.parent_entity_type === "character") {
    const sectionByType = {
      alias: "aliases",
      cultivation: "cultivation",
      character_skill: "skills",
      character_item: "items",
    };
    return `${basePath}?entity=characters&section=${sectionByType[log.entity_type] || "basic"}&character=${log.parent_entity_id}`;
  }

  if (log.parent_entity_type === "skill") return `${basePath}?entity=skills&section=characters&skill=${log.parent_entity_id}`;
  if (log.parent_entity_type === "item") return `${basePath}?entity=items&section=characters&item=${log.parent_entity_id}`;

  return basePath;
}

function ChangeDetailRow({ icon: Icon, label, children, tone }) {
  if (!children && children !== 0) return null;

  return (
    <div className={`edit-log-detail-row ${tone || ""}`}>
      <span>
        <Icon aria-hidden="true" size={16} />
        {label}
      </span>
      <strong>{children}</strong>
    </div>
  );
}

export default function WikiEditLogPage({ novel }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [logs, setLogs] = React.useState([]);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [pagination, setPagination] = React.useState({
    page: 1,
    per_page: 10,
    total: 0,
    total_pages: 1,
  });
  const [selectedLogId, setSelectedLogId] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const filters = {
    search: searchParams.get("search") || "",
    entity_type: searchParams.get("entity_type") || "all",
    change_type: searchParams.get("change_type") || "all",
    date_range: searchParams.get("date_range") || "all",
    edited_by: searchParams.get("edited_by") || "all",
    page: Math.max(Number(searchParams.get("page")) || 1, 1),
    per_page: Number(searchParams.get("per_page")) || 10,
  };

  function updateFilters(nextValues) {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(nextValues).forEach(([key, value]) => {
      if (!value || value === "all" || (key === "page" && Number(value) <= 1)) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    setSearchParams(nextParams, { replace: false });
  }

  function resetFilters() {
    setSearchParams(new URLSearchParams(), { replace: false });
  }

  React.useEffect(() => {
    if (!novel?.id) return undefined;

    const controller = new AbortController();

    async function loadLogs() {
      setLoading(true);
      setError("");

      try {
        const params = new URLSearchParams();
        params.set("page", String(filters.page));
        params.set("per_page", String(filters.per_page));
        if (filters.search) params.set("search", filters.search);
        if (filters.entity_type !== "all") params.set("entity_type", filters.entity_type);
        if (filters.change_type !== "all") params.set("change_type", filters.change_type);
        if (filters.edited_by !== "all") params.set("edited_by", filters.edited_by);

        const dateParams = dateRangeParams(filters.date_range);
        Object.entries(dateParams).forEach(([key, value]) => params.set(key, value));

        const data = await fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novel.id}/edit-log?${params.toString()}`, {
          signal: controller.signal,
        });
        setLogs(data.logs || []);
        setPagination(data.pagination || pagination);
      } catch (requestError) {
        if (requestError.name !== "AbortError") {
          setError(requestError.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadLogs();
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novel?.id, searchParams]);

  React.useEffect(() => {
    if (!logs.length) {
      setSelectedLogId(null);
      return;
    }

    if (!logs.some((log) => log.id === selectedLogId)) {
      setSelectedLogId(logs[0].id);
    }
  }, [logs, selectedLogId]);

  const selectedLog = logs.find((log) => log.id === selectedLogId) || null;
  const groupedLogs = groupLogs(logs);
  const pages = pageWindow(pagination.page, pagination.total_pages);
  const startIndex = pagination.total ? (pagination.page - 1) * pagination.per_page + 1 : 0;
  const endIndex = Math.min(pagination.page * pagination.per_page, pagination.total);
  const publicWikiPath = `/wiki/novels/${novel?.id}`;
  const activeFilterCount = [
    filters.search,
    filters.entity_type !== "all",
    filters.change_type !== "all",
    filters.date_range !== "all",
    filters.edited_by !== "all",
  ].filter(Boolean).length;

  return (
    <div className="workspace-page editor-page edit-log-page">
      <header className="workspace-page-header">
        <div>
          <h1>Wiki Edit Log</h1>
          <p>View history of canonical wiki data changes made by admins.</p>
        </div>
        <div className="workspace-header-actions">
          <button type="button" className="admin-secondary-button" onClick={() => window.open(publicWikiPath, "_blank", "noopener,noreferrer")}>
            View Public Wiki
            <ExternalLink aria-hidden="true" size={15} />
          </button>
        </div>
      </header>

      <section className="edit-log-page-body">
        <section className={`edit-log-filter-panel admin-panel ${filtersOpen ? "open" : ""}`}>
          <button
            type="button"
            className="edit-log-filter-toggle"
            onClick={() => setFiltersOpen((isOpen) => !isOpen)}
            aria-expanded={filtersOpen}
          >
            <span>
              <Filter aria-hidden="true" size={18} />
              Filters
              {activeFilterCount ? <strong>{activeFilterCount}</strong> : null}
            </span>
            <ChevronDown aria-hidden="true" size={18} />
          </button>
          <div className="edit-log-filter-bar">
            <label className="edit-log-search-field editor-search-field" htmlFor="edit-log-search">
              <Search aria-hidden="true" size={18} />
              <input
                id="edit-log-search"
                type="search"
                value={filters.search}
                placeholder="Search changes..."
                onChange={(event) => updateFilters({ search: event.target.value, page: 1 })}
              />
            </label>
            <label>
              <span>Entity Type</span>
              <select value={filters.entity_type} onChange={(event) => updateFilters({ entity_type: event.target.value, page: 1 })}>
                {ENTITY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>Change Type</span>
              <select value={filters.change_type} onChange={(event) => updateFilters({ change_type: event.target.value, page: 1 })}>
                {CHANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>Date Range</span>
              <select value={filters.date_range} onChange={(event) => updateFilters({ date_range: event.target.value, page: 1 })}>
                {DATE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>Admin</span>
              <select value={filters.edited_by} onChange={(event) => updateFilters({ edited_by: event.target.value, page: 1 })}>
                <option value="all">All</option>
                <option value="Admin">Admin</option>
              </select>
            </label>
            <button type="button" className="admin-secondary-button" onClick={resetFilters}>
              <FilterX aria-hidden="true" size={16} />
              Reset Filters
            </button>
          </div>
        </section>

        <section className="edit-log-layout">
          <div className="edit-log-main">
            {error ? <div className="admin-message danger">{error}</div> : null}
            {loading ? <div className="editor-empty-state">Loading edit log...</div> : null}
            {!loading && !logs.length ? (
              <div className="editor-empty-state">
                No edit log entries yet. Canonical wiki changes saved in the Wiki Data Editor will appear here.
              </div>
            ) : null}

            {!loading && groupedLogs.map((group) => (
              <section className="edit-log-group" key={group.label}>
                <header>
                  <h2>{group.label}</h2>
                  <span>{group.logs.length} {group.logs.length === 1 ? "change" : "changes"}</span>
                </header>
                <div className="edit-log-row-list">
                  {group.logs.map((log) => {
                    const Icon = changeIcon(log.change_type);
                    const entityLabel = rowEntityLabel(log);
                    const oldValue = shortText(log.old_value);
                    const newValue = shortText(log.new_value);
                    const contextValue = shortText(contextualChangeText(log));
                    const changedValue = newValue || oldValue || "";

                    return (
                      <button
                        type="button"
                        className={`edit-log-row ${selectedLogId === log.id ? "active" : ""} ${log.change_type}`}
                        key={log.id}
                        onClick={() => setSelectedLogId(log.id)}
                      >
                        <span className="edit-log-row-icon">
                          <Icon aria-hidden="true" size={18} />
                        </span>
                        <span className="edit-log-change-badge">{log.change_type}</span>
                        <span className="edit-log-entity">
                          <strong>{entityLabel}</strong>
                          <small>{log.field_name || log.entity_type}</small>
                        </span>
                        <span className="edit-log-summary">
                          {log.change_type === "updated" && oldValue && newValue ? (
                            <>
                              <span>{oldValue}</span>
                              <ChevronRight aria-hidden="true" size={15} />
                              <strong>{newValue}</strong>
                            </>
                          ) : contextValue && changedValue ? (
                            <>
                              <strong>{changedValue}</strong>
                              <span>{contextValue}</span>
                            </>
                          ) : (
                            <strong>{contextValue || newValue || oldValue || log.summary}</strong>
                          )}
                        </span>
                        <span className="edit-log-admin">
                          <strong>{log.edited_by || "Admin"}</strong>
                          <small>{formatDate(log.created_at, { hour: "2-digit", minute: "2-digit" })}</small>
                        </span>
                        <ChevronRight className="edit-log-row-chevron" aria-hidden="true" size={18} />
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}

            <footer className="edit-log-pagination">
              <div>
                <button type="button" disabled={pagination.page <= 1} onClick={() => updateFilters({ page: pagination.page - 1 })}>
                  Previous
                </button>
                {pages.map((page) => (
                  <button
                    type="button"
                    className={page === pagination.page ? "active" : ""}
                    key={page}
                    onClick={() => updateFilters({ page })}
                  >
                    {page}
                  </button>
                ))}
                {pagination.total_pages > 3 ? <span>...</span> : null}
                {pagination.total_pages > 3 ? (
                  <button
                    type="button"
                    className={pagination.total_pages === pagination.page ? "active" : ""}
                    onClick={() => updateFilters({ page: pagination.total_pages })}
                  >
                    {pagination.total_pages}
                  </button>
                ) : null}
                <button type="button" disabled={pagination.page >= pagination.total_pages} onClick={() => updateFilters({ page: pagination.page + 1 })}>
                  Next
                </button>
              </div>
              <p>Showing {startIndex} to {endIndex} of {pagination.total} changes</p>
              <select value={filters.per_page} onChange={(event) => updateFilters({ per_page: event.target.value, page: 1 })}>
                {PER_PAGE_OPTIONS.map((option) => <option key={option} value={option}>{option} / page</option>)}
              </select>
            </footer>
          </div>

          <aside className="edit-log-detail-panel admin-panel">
            {selectedLog ? (
              <>
                <header>
                  <h2>Change Details</h2>
                </header>
                <div className="edit-log-detail-list">
                  <ChangeDetailRow icon={FileClock} label="Action" tone={selectedLog.change_type}>
                    <span className={`edit-log-change-badge ${selectedLog.change_type}`}>{selectedLog.change_type}</span>
                  </ChangeDetailRow>
                  <ChangeDetailRow icon={Info} label="Entity">{rowEntityLabel(selectedLog)}</ChangeDetailRow>
                  <ChangeDetailRow icon={Info} label="Changed Record">{changedRecordLabel(selectedLog)}</ChangeDetailRow>
                  <ChangeDetailRow icon={ListChecks} label="Field">{selectedLog.field_name}</ChangeDetailRow>
                  <ChangeDetailRow icon={Calendar} label="Old Value">{valueText(selectedLog.old_value)}</ChangeDetailRow>
                  <ChangeDetailRow icon={Calendar} label="New Value">{valueText(selectedLog.new_value)}</ChangeDetailRow>
                  <ChangeDetailRow icon={ListChecks} label="Summary">{selectedLog.summary}</ChangeDetailRow>
                  <ChangeDetailRow icon={UserRound} label="Edited By">{selectedLog.edited_by || "Admin"}</ChangeDetailRow>
                  <ChangeDetailRow icon={Calendar} label="Time">
                    {formatDate(selectedLog.created_at, { month: "long", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </ChangeDetailRow>
                </div>
                <div className="edit-log-quick-actions">
                  <button type="button" className="admin-primary-button" onClick={() => navigate(editorPathForLog(selectedLog, novel.id))}>
                    Open in Editor
                  </button>
                  <button type="button" className="admin-secondary-button" onClick={() => window.open(publicPathForLog(selectedLog, novel), "_blank", "noopener,noreferrer")}>
                    View Public Page
                    <ExternalLink aria-hidden="true" size={15} />
                  </button>
                </div>
              </>
            ) : (
              <div className="editor-empty-state">Select an edit log row to inspect the change.</div>
            )}
          </aside>
        </section>
      </section>
    </div>
  );
}
