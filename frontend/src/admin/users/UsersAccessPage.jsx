import React from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  CircleCheck,
  CircleX,
  Copy,
  Edit3,
  Eye,
  Info,
  Link as LinkIcon,
  Mail,
  Plus,
  Save,
  Search,
  Shield,
  ShieldCheck,
  ShieldAlert,
  User,
  UserMinus,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import EmptyState from "../components/EmptyState.jsx";

const EMPTY_USER_FORM = {
  username: "",
  email: "",
  role: "editor",
  is_active: true,
};

function initials(value) {
  const parts = String(value || "")
    .replace(/@.*/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return String(value || "U").slice(0, 2).toUpperCase();
}

function formatDate(value) {
  if (!value) return "Never";

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function relativeLogin(value) {
  if (!value) return "Never";

  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.round(diffMs / 60000));

  if (minutes < 60) return `${minutes} min ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;

  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function StatCard({ count, icon: Icon, label, tone }) {
  return (
    <article className={`users-stat-card ${tone}`}>
      <span>
        <Icon aria-hidden="true" size={24} strokeWidth={1.9} />
      </span>
      <div>
        <strong>{count}</strong>
        <small>{label}</small>
      </div>
    </article>
  );
}

function roleHelpText(role) {
  if (role === "editor") {
    return "Editors can edit assigned novels and review extraction data.";
  }

  if (role === "superadmin") {
    return "Superadmin role is managed by the secure bootstrap flow.";
  }

  return "Users can browse the public wiki and manage their own account.";
}

function UserFormModal({ currentUser, initialUser, onClose, onDeactivate, onGenerateReset, onSave, setupLink }) {
  const [localError, setLocalError] = React.useState("");
  const [form, setForm] = React.useState(() => ({
    ...EMPTY_USER_FORM,
    ...(initialUser || {}),
    role: initialUser?.role || EMPTY_USER_FORM.role,
  }));
  const isEditing = Boolean(initialUser);
  const canDeactivate = isEditing && initialUser?.is_active && currentUser?.id !== initialUser?.id;
  const canActivate = isEditing && !initialUser?.is_active;

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSave(form);
  }

  async function copySetupLink() {
    if (!setupLink) return;

    await navigator.clipboard?.writeText(setupLink);
  }

  async function handleGenerateReset() {
    setLocalError("");

    if (!form.is_active) {
      setLocalError("Activate this user before generating a password reset link.");
      return;
    }

    try {
      await onGenerateReset(initialUser);
    } catch (error) {
      setLocalError(error.message);
    }
  }

  return (
    <div className="admin-modal-backdrop users-modal-backdrop">
      <form className="admin-modal users-modal edit-user-modal-shell" onSubmit={handleSubmit}>
        <div className="admin-modal-header users-modal-header edit-user-header">
          <div>
            <h2 className="edit-user-title">{isEditing ? "Edit User" : "Create / Invite User"}</h2>
            {!isEditing ? (
              <p className="edit-user-subtitle">Create a new editor or user. They will set their password using a secure link.</p>
            ) : null}
          </div>
          <button className="edit-user-close" type="button" onClick={onClose} aria-label="Close">
            <X aria-hidden="true" size={19} strokeWidth={1.9} />
          </button>
        </div>

        {isEditing ? (
          <>
          <div className="edit-user-identity">
            <span className="edit-user-avatar">{initials(initialUser.username)}</span>
            <div>
              <strong className="edit-user-name">{initialUser.username}</strong>
              <div className="edit-user-email">{initialUser.email}</div>
              <span className="edit-user-badges">
                <span className="edit-user-badge edit-user-badge--role">{initialUser.role}</span>
                <span className={initialUser.is_active ? "edit-user-badge edit-user-badge--active" : "edit-user-badge edit-user-badge--inactive"}>
                  {initialUser.is_active ? "Active" : "Inactive"}
                </span>
              </span>
            </div>
          </div>
          <div className="edit-user-divider" />
          </>
        ) : null}

        {!isEditing ? <div className="edit-user-divider create-user-divider" /> : null}

        <div className="edit-user-form">
          <label className="edit-user-field">
            <span className="edit-user-label">Display Name</span>
            <span className="edit-user-input-wrap">
              <User className="edit-user-input-icon" aria-hidden="true" size={18} strokeWidth={1.9} />
              <input
                className="edit-user-input"
                value={form.username}
                onChange={(event) => updateField("username", event.target.value)}
                placeholder="Enter display name"
              />
            </span>
          </label>
          <label className="edit-user-field">
            <span className="edit-user-label">Email</span>
            <span className="edit-user-input-wrap">
              <Mail className="edit-user-input-icon" aria-hidden="true" size={18} strokeWidth={1.9} />
              <input
                className="edit-user-input"
                type="email"
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                placeholder="Enter email address"
              />
            </span>
          </label>
          <label className="edit-user-field">
            <span className="edit-user-label">Role</span>
            {initialUser?.role === "superadmin" ? (
              <span className="edit-user-input-wrap">
                <Shield className="edit-user-input-icon" aria-hidden="true" size={18} strokeWidth={1.9} />
                <input className="edit-user-input" readOnly value="Superadmin" />
              </span>
            ) : (
              <span className="edit-user-input-wrap">
                <Shield className="edit-user-input-icon" aria-hidden="true" size={18} strokeWidth={1.9} />
                <select className="edit-user-select" value={form.role} onChange={(event) => updateField("role", event.target.value)}>
                  <option value="editor">Editor</option>
                  <option value="user">User</option>
                </select>
                <ChevronDown className="edit-user-select-chevron" aria-hidden="true" size={20} strokeWidth={2} />
              </span>
            )}
            <small className="edit-user-helper">{roleHelpText(form.role)}</small>
          </label>
          {!isEditing ? (
            <label className="edit-user-active-row">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => updateField("is_active", event.target.checked)}
              />
              <span>
                <strong>Active Account</strong>
                <small>Active users can sign in and access the system.</small>
              </span>
            </label>
          ) : null}
        </div>

        {!isEditing ? (
          <div className="edit-user-info-box">
            <Info aria-hidden="true" size={22} strokeWidth={1.9} />
            <p>A password setup link will be generated after creating the user. Share that link so they can set their own password.</p>
          </div>
        ) : (
          <div className="edit-user-account-actions">
            <div className="edit-user-section-divider" />
            <h3 className="edit-user-actions-section-title">Account Actions</h3>
            <p className="edit-user-actions-section-text">Send the user a link to set or reset their password.</p>
            <button
              className="edit-user-reset-link-btn"
              disabled={!form.is_active}
              title={!form.is_active ? "Activate this user before generating a reset link." : "Generate a password reset link"}
              type="button"
              onClick={handleGenerateReset}
            >
              <LinkIcon aria-hidden="true" size={16} strokeWidth={1.9} />
              Generate Password Reset Link
            </button>
            {localError ? <div className="edit-user-inline-error">{localError}</div> : null}
          </div>
        )}

        {setupLink ? (
          <div className="users-setup-link-box">
            <strong>{isEditing ? "Password reset link generated." : "User created successfully."}</strong>
            <small>Copy this link and send it to the user. It expires in 24 hours and can only be used once.</small>
            <div>
              <input readOnly value={setupLink} />
              <button className="secondary" type="button" onClick={copySetupLink}>
                <Copy aria-hidden="true" size={15} strokeWidth={1.9} />
                Copy
              </button>
            </div>
          </div>
        ) : null}

        <div className="edit-user-footer">
          <button className="edit-user-btn edit-user-btn--secondary" type="button" onClick={onClose}>Cancel</button>
          {canDeactivate ? (
            <button className="edit-user-btn edit-user-btn--danger" type="button" onClick={() => onDeactivate(initialUser)}>
              <UserMinus aria-hidden="true" size={16} strokeWidth={1.9} />
              Deactivate User
            </button>
          ) : null}
          {canActivate ? (
            <button
              className="edit-user-btn edit-user-btn--activate"
              type="button"
              onClick={() => onSave({ ...form, is_active: true })}
            >
              <CircleCheck aria-hidden="true" size={16} strokeWidth={1.9} />
              Activate User
            </button>
          ) : null}
          <button className="edit-user-btn edit-user-btn--primary" type="submit">
            {isEditing ? <Save aria-hidden="true" size={16} strokeWidth={1.9} /> : <UserPlus aria-hidden="true" size={16} strokeWidth={1.9} />}
            {isEditing ? "Save Changes" : "Create User"}
          </button>
        </div>
        {isEditing ? (
          <aside className="edit-user-warning">
            <ShieldAlert className="edit-user-warning-icon" aria-hidden="true" size={30} strokeWidth={1.9} />
            <div>
              <strong className="edit-user-warning-title">Important</strong>
              <p className="edit-user-warning-text">Deactivating a user will prevent them from signing in, but their data and edit history will be preserved.</p>
            </div>
          </aside>
        ) : null}
      </form>
    </div>
  );
}

function SearchField({ onChange, placeholder, value }) {
  return (
    <label className="users-search-field">
      <Search aria-hidden="true" size={16} strokeWidth={1.9} />
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

function UsersPanel({ currentUser, onEdit, users }) {
  const [query, setQuery] = React.useState("");
  const filteredUsers = users.filter((user) =>
    `${user.username} ${user.email} ${user.role}`.toLowerCase().includes(query.trim().toLowerCase())
  );

  return (
    <section className="admin-panel users-panel">
      <div className="users-panel-header">
        <div>
          <h2>Users</h2>
          <p>{users.length} accounts</p>
        </div>
        <SearchField value={query} onChange={setQuery} placeholder="Search users..." />
      </div>

      {filteredUsers.length ? (
        <div className="admin-data-list users-list compact">
          {filteredUsers.map((user, index) => {
            return (
              <article className="admin-data-row users-row compact" key={user.id}>
                <span className={`users-mobile-avatar users-avatar tone-${index % 6}`}>{initials(user.username)}</span>
                <div className="users-primary">
                  <strong>{user.username}</strong>
                  <small>{user.email}</small>
                </div>
                <div className="users-meta-badges">
                  <span className={`users-role ${user.role}`}>{user.role}</span>
                  <span
                    className={user.is_active ? "users-status-icon active" : "users-status-icon inactive"}
                    title={user.is_active ? "Active account" : "Inactive account"}
                    aria-label={user.is_active ? "Active account" : "Inactive account"}
                  >
                    {user.is_active ? (
                      <CircleCheck aria-hidden="true" size={21} strokeWidth={2} />
                    ) : (
                      <CircleX aria-hidden="true" size={21} strokeWidth={2} />
                    )}
                    <span className="users-status-label">{user.is_active ? "Active" : "Inactive"}</span>
                  </span>
                </div>
                <div className="users-last-login">
                  <small>Last login</small>
                  <strong>{relativeLogin(user.last_login_at)}</strong>
                </div>
                <button className="users-edit-button" title="Edit user" aria-label={`Edit ${user.username}`} type="button" onClick={() => onEdit(user)}>
                  <Edit3 aria-hidden="true" size={14} strokeWidth={1.9} />
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState title="No matching users" message="Try a different search term." />
      )}

      <div className="users-panel-footer">
        <button disabled type="button">‹</button>
        <button className="active" type="button">1</button>
        <button disabled type="button">2</button>
        <button disabled type="button">3</button>
        <button disabled type="button">›</button>
        <select defaultValue="10">
          <option value="10">10 per page</option>
        </select>
      </div>
    </section>
  );
}

function CapabilityCard({ checked, description, disabled = false, icon: Icon, label, onChange }) {
  return (
    <button
      className={`${checked ? "users-capability-card selected" : "users-capability-card"}${disabled ? " disabled" : ""}`}
      disabled={disabled}
      type="button"
      onClick={() => onChange(!checked)}
    >
      <span className="users-capability-check">{checked ? <Check aria-hidden="true" size={17} /> : null}</span>
      <Icon aria-hidden="true" size={30} strokeWidth={1.9} />
      <strong>{label}</strong>
      <small>{description}</small>
    </button>
  );
}

function AssignPermissionsPanel({
  onAddAccess,
  permissionForm,
  selectedNovelId,
  selectedUserId,
  setPermissionForm,
  setSelectedNovelId,
  setSelectedUserId,
  users,
  novels,
}) {
  const editorUsers = users.filter((user) => user.role !== "user" && user.is_active);
  const selectedUser = users.find((user) => String(user.id) === String(selectedUserId));
  const isSelectedSuperadmin = selectedUser?.role === "superadmin";

  function updateSelectedUser(userId) {
    setSelectedUserId(userId);
    const nextUser = users.find((user) => String(user.id) === String(userId));

    if (nextUser?.role === "superadmin") {
      setPermissionForm({
        can_edit: true,
        can_review: true,
        can_approve: true,
      });
    }
  }

  return (
    <section className="admin-panel users-assign-panel">
      <div className="admin-section-header">
        <div>
          <h2>Assign Novel Permissions</h2>
          <p>Assign edit, review, and approve access to editors for specific novels.</p>
        </div>
      </div>

      <div className="users-assign-selects">
        <label>
          <span>Select Novel</span>
          <select value={selectedNovelId} onChange={(event) => setSelectedNovelId(event.target.value)}>
            <option value="">Select novel</option>
            {novels.map((novel) => (
              <option key={novel.id} value={novel.id}>{novel.title}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Select User</span>
          <select value={selectedUserId} onChange={(event) => updateSelectedUser(event.target.value)}>
            <option value="">Select editor</option>
            {editorUsers.map((user) => (
              <option key={user.id} value={user.id}>{user.username} ({user.email})</option>
            ))}
          </select>
        </label>
      </div>

      <h3>Capabilities</h3>
      <div className="users-capability-grid">
        <CapabilityCard
          checked={permissionForm.can_edit}
          description="Can create and edit wiki content"
          disabled={isSelectedSuperadmin}
          icon={Edit3}
          label="Edit Wiki Data"
          onChange={(value) => setPermissionForm((current) => ({ ...current, can_edit: value }))}
        />
        <CapabilityCard
          checked={permissionForm.can_review}
          description="Can review extracted data and proposals"
          disabled={isSelectedSuperadmin}
          icon={Eye}
          label="Review Extraction"
          onChange={(value) => setPermissionForm((current) => ({ ...current, can_review: value }))}
        />
        <CapabilityCard
          checked={permissionForm.can_approve}
          description="Can approve and publish changes"
          disabled={isSelectedSuperadmin}
          icon={ShieldCheck}
          label="Approve Changes"
          onChange={(value) => setPermissionForm((current) => ({ ...current, can_approve: value }))}
        />
      </div>
      {isSelectedSuperadmin ? (
        <p className="users-superadmin-note">
          Superadmins already have full access to every novel. Novel-specific permissions cannot be disabled.
        </p>
      ) : null}

      <button className="users-add-access-button" disabled={isSelectedSuperadmin} type="button" onClick={onAddAccess}>
        <ShieldCheck aria-hidden="true" size={16} strokeWidth={1.9} />
        Add Access
      </button>
    </section>
  );
}

function AccessAssignments({ assignments, onDelete, onEdit }) {
  const [query, setQuery] = React.useState("");
  const filteredAssignments = assignments.filter((permission) =>
    `${permission.novel_title} ${permission.username} ${permission.email || ""}`.toLowerCase().includes(query.trim().toLowerCase())
  );

  return (
    <section className="admin-panel users-access-table-panel">
      <div className="users-panel-header">
        <div>
          <h2>Current Access Assignments</h2>
          <p>View and manage existing novel access for all users.</p>
        </div>
        <SearchField value={query} onChange={setQuery} placeholder="Search access..." />
      </div>

      <div className="users-access-table">
        <div className="users-access-head">
          <span>Novel</span>
          <span>User</span>
          <span>Role</span>
          <span>Edit</span>
          <span>Review</span>
          <span>Approve</span>
          <span>Assigned On</span>
          <span>Actions</span>
        </div>
        {filteredAssignments.map((permission) => (
          <article className="users-access-row" key={permission.id}>
            <strong>{permission.novel_title}</strong>
            <div className="users-access-user">
              <span>
                <strong>{permission.username}</strong>
                <small>{permission.email}</small>
              </span>
            </div>
            <span className="users-role editor">Editor</span>
            {["can_edit", "can_review", "can_approve"].map((field) => (
              <span className={permission[field] ? "users-yes" : "users-no"} key={field}>
                {permission[field] ? <Check aria-hidden="true" size={15} /> : <X aria-hidden="true" size={15} />}
                {permission[field] ? "Yes" : "No"}
              </span>
            ))}
            <span>{formatDate(permission.created_at)}</span>
            <span className="users-access-actions">
              <button className="secondary" type="button" onClick={() => onEdit(permission)}>Edit</button>
              <button className="danger ghost" type="button" onClick={() => onDelete(permission)} aria-label="Remove access">
                <Trash2 aria-hidden="true" size={15} strokeWidth={1.9} />
              </button>
            </span>
          </article>
        ))}
      </div>

      <div className="users-access-mobile-list">
        {filteredAssignments.map((permission) => (
          <article className="users-access-mobile-card" key={permission.id}>
            <div className="users-access-mobile-main">
              <span className="users-access-mobile-icon">
                <BookOpen aria-hidden="true" size={22} strokeWidth={1.9} />
              </span>
              <div>
                <strong>{permission.novel_title}</strong>
                <span>{permission.username}</span>
                <small>{permission.email}</small>
              </div>
            </div>
            <div className="users-access-mobile-permissions">
              {[
                ["can_edit", "Edit"],
                ["can_review", "Review"],
                ["can_approve", "Approve"],
              ].map(([field, label]) => (
                <span className={permission[field] ? "users-yes" : "users-no"} key={field}>
                  {permission[field] ? <Check aria-hidden="true" size={15} /> : <X aria-hidden="true" size={15} />}
                  {label}
                </span>
              ))}
            </div>
            <div className="users-access-mobile-footer">
              <span>Assigned: {formatDate(permission.created_at)}</span>
              <span className="users-access-actions">
                <button className="secondary" type="button" onClick={() => onEdit(permission)}>Edit</button>
                <button className="danger ghost" type="button" onClick={() => onDelete(permission)} aria-label="Remove access">
                  <Trash2 aria-hidden="true" size={15} strokeWidth={1.9} />
                </button>
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function UsersAccessPage() {
  const { currentUser } = useAuth();
  const [data, setData] = React.useState({ users: [], novels: [] });
  const [editingUser, setEditingUser] = React.useState(null);
  const [editingPermission, setEditingPermission] = React.useState(null);
  const [isCreatingUser, setIsCreatingUser] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [passwordSetupLink, setPasswordSetupLink] = React.useState("");
  const [selectedUserId, setSelectedUserId] = React.useState("");
  const [selectedNovelId, setSelectedNovelId] = React.useState("");
  const [permissions, setPermissions] = React.useState([]);
  const [permissionForm, setPermissionForm] = React.useState({
    can_edit: true,
    can_review: true,
    can_approve: false,
  });

  const userEmailById = React.useMemo(
    () => Object.fromEntries(data.users.map((user) => [user.id, user.email])),
    [data.users]
  );
  const enrichedPermissions = permissions.map((permission) => ({
    ...permission,
    email: userEmailById[permission.user_id],
  }));
  const stats = {
    editors: data.users.filter((user) => user.role === "editor").length,
    novels: data.novels.length,
    superadmins: data.users.filter((user) => user.role === "superadmin").length,
    users: data.users.filter((user) => user.role === "user").length,
  };

  async function loadUsersAndPermissions() {
    const payload = await fetchJson(`${API_BASE_URL}/admin/users`);
    setData(payload);

    const permissionPayloads = await Promise.all(
      (payload.novels || []).map((novel) =>
        fetchJson(`${API_BASE_URL}/admin/novels/${novel.id}/permissions`)
          .then((response) => response.permissions || [])
      )
    );
    setPermissions(permissionPayloads.flat());
  }

  React.useEffect(() => {
    loadUsersAndPermissions().catch((error) => setMessage(error.message));
  }, []);

  async function saveUser(form) {
    try {
      const isEditing = Boolean(editingUser);
      const wasInactive = isEditing && editingUser && !editingUser.is_active;
      const payload = {
        username: form.username,
        email: form.email,
        role: form.role,
        is_active: form.is_active,
      };

      const response = await fetchJson(`${API_BASE_URL}/admin/users${isEditing ? `/${editingUser.id}` : ""}`, {
        method: isEditing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.password_setup?.setup_path) {
        setPasswordSetupLink(`${window.location.origin}${response.password_setup.setup_path}`);
      } else {
        setEditingUser(null);
        setIsCreatingUser(false);
        setPasswordSetupLink("");
        setMessage(wasInactive && payload.is_active ? `${payload.username} activated.` : isEditing ? "User updated." : "User created.");
      }
      await loadUsersAndPermissions();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function generatePasswordReset(user) {
    const response = await fetchJson(`${API_BASE_URL}/admin/users/${user.id}/password-reset`, {
      method: "POST",
    });
    setPasswordSetupLink(`${window.location.origin}${response.password_setup.setup_path}`);
    await loadUsersAndPermissions();
  }

  async function deactivateUser(user) {
    if (currentUser?.id === user.id) {
      return;
    }

    await fetchJson(`${API_BASE_URL}/admin/users/${user.id}`, { method: "DELETE" });
    setEditingUser(null);
    setIsCreatingUser(false);
    setPasswordSetupLink("");
    setMessage(`${user.username} deactivated.`);
    await loadUsersAndPermissions();
  }

  async function createPermission() {
    const selectedUser = data.users.find((user) => String(user.id) === String(selectedUserId));

    if (selectedUser?.role === "superadmin") {
      setPermissionForm({
        can_edit: true,
        can_review: true,
        can_approve: true,
      });
      setMessage("Superadmins already have full access to every novel.");
      return;
    }

    if (!selectedNovelId || !selectedUserId) {
      setMessage("Select both a user and a novel.");
      return;
    }

    if (!permissionForm.can_edit && !permissionForm.can_review && !permissionForm.can_approve) {
      setMessage("Select at least one capability.");
      return;
    }

    try {
      if (editingPermission) {
        await fetchJson(`${API_BASE_URL}/admin/novels/${editingPermission.novel_id}/permissions/${editingPermission.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(permissionForm),
        });
        setEditingPermission(null);
      } else {
        await fetchJson(`${API_BASE_URL}/admin/novels/${selectedNovelId}/permissions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: Number(selectedUserId),
            ...permissionForm,
          }),
        });
      }
      await loadUsersAndPermissions();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function deletePermission(permission) {
    if (!window.confirm(`Remove access for ${permission.username} on ${permission.novel_title}?`)) {
      return;
    }

    await fetchJson(`${API_BASE_URL}/admin/novels/${permission.novel_id}/permissions/${permission.id}`, {
      method: "DELETE",
    });
    await loadUsersAndPermissions();
  }

  function editPermission(permission) {
    setEditingPermission(permission);
    setSelectedNovelId(String(permission.novel_id));
    setSelectedUserId(String(permission.user_id));
    setPermissionForm({
      can_edit: permission.can_edit,
      can_review: permission.can_review,
      can_approve: permission.can_approve,
    });
  }

  return (
    <div className="users-access-page redesigned">
      <div className="admin-page-header">
        <div>
          <h1>Users & Access</h1>
          <p>Manage admin accounts and novel-level editor permissions.</p>
        </div>
        <div className="admin-header-actions">
          <button className="secondary" disabled type="button">
            <UserPlus aria-hidden="true" size={17} strokeWidth={1.9} />
            Invite User
          </button>
          <button
            type="button"
            onClick={() => {
              setPasswordSetupLink("");
              setIsCreatingUser(true);
            }}
          >
            <Plus aria-hidden="true" size={17} strokeWidth={1.9} />
            Create User
          </button>
        </div>
      </div>

      {message ? <div className="admin-message">{message}</div> : null}

      <section className="users-stat-grid">
        <StatCard count={stats.superadmins} icon={Shield} label="Superadmin" tone="purple" />
        <StatCard count={stats.editors} icon={Users} label="Editors" tone="blue" />
        <StatCard count={stats.users} icon={Users} label="Users" tone="green" />
        <StatCard count={stats.novels} icon={BookOpen} label="Novels" tone="orange" />
      </section>

      <section className="users-access-grid redesigned">
        <UsersPanel
          currentUser={currentUser}
          users={data.users}
          onEdit={(user) => {
            setPasswordSetupLink("");
            setEditingUser(user);
          }}
        />
        <AssignPermissionsPanel
          novels={data.novels}
          users={data.users}
          selectedNovelId={selectedNovelId}
          selectedUserId={selectedUserId}
          setSelectedNovelId={setSelectedNovelId}
          setSelectedUserId={setSelectedUserId}
          permissionForm={permissionForm}
          setPermissionForm={setPermissionForm}
          onAddAccess={createPermission}
        />
      </section>

      <AccessAssignments
        assignments={enrichedPermissions}
        onDelete={deletePermission}
        onEdit={editPermission}
      />

      {isCreatingUser || editingUser ? (
        <UserFormModal
          initialUser={editingUser}
          currentUser={currentUser}
          onClose={() => {
            setIsCreatingUser(false);
            setEditingUser(null);
            setPasswordSetupLink("");
          }}
          onDeactivate={deactivateUser}
          onGenerateReset={generatePasswordReset}
          onSave={saveUser}
          setupLink={passwordSetupLink}
        />
      ) : null}
    </div>
  );
}
