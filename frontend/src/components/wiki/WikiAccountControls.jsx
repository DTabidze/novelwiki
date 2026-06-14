import React from "react";
import {
  Bell,
  ChevronDown,
  Gauge,
  LogIn,
  LogOut,
  Settings,
  User,
  UserCog,
  UserPlus,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext.jsx";

function initialsForUser(user) {
  const source = user?.username || user?.email || "";
  const parts = source
    .replace(/@.*/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return source.slice(0, 2).toUpperCase() || "U";
}

function roleLabel(role) {
  if (role === "superadmin") return "Superadmin";
  if (role === "editor") return "Editor";
  return "User";
}

function AccountMenuItem({ children, danger = false, icon: Icon, onClick }) {
  return (
    <button className={danger ? "wiki-account-menu-item danger" : "wiki-account-menu-item"} type="button" onClick={onClick}>
      <Icon aria-hidden="true" size={16} strokeWidth={1.9} />
      {children}
    </button>
  );
}

export default function WikiAccountControls() {
  const { currentUser, isEditor, isSuperadmin, logout } = useAuth();
  const navigate = useNavigate();
  const accountRef = React.useRef(null);
  const notificationsRef = React.useRef(null);
  const [isAccountOpen, setIsAccountOpen] = React.useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = React.useState(false);
  const canOpenAdmin = isSuperadmin || (isEditor && (currentUser?.permissions || []).length > 0);

  React.useEffect(() => {
    function handlePointerDown(event) {
      if (accountRef.current && !accountRef.current.contains(event.target)) {
        setIsAccountOpen(false);
      }

      if (notificationsRef.current && !notificationsRef.current.contains(event.target)) {
        setIsNotificationsOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsAccountOpen(false);
        setIsNotificationsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  async function handleLogout() {
    await logout();
    setIsAccountOpen(false);
    navigate("/wiki/novels");
  }

  return (
    <div className="wiki-header-actions">
      <div className="wiki-notification-wrap" ref={notificationsRef}>
        <button
          aria-expanded={isNotificationsOpen}
          aria-label="Notifications"
          className="wiki-header-icon-button"
          type="button"
          onClick={() => {
            setIsNotificationsOpen((open) => !open);
            setIsAccountOpen(false);
          }}
        >
          <Bell aria-hidden="true" size={20} strokeWidth={1.9} />
        </button>
        {isNotificationsOpen ? (
          <div className="wiki-header-popover wiki-notification-popover">
            <h3>Notifications</h3>
            <p>No notifications yet.</p>
          </div>
        ) : null}
      </div>

      <div className="wiki-account-wrap" ref={accountRef}>
        <button
          aria-expanded={isAccountOpen}
          aria-label="User menu"
          className="wiki-account-trigger"
          type="button"
          onClick={() => {
            setIsAccountOpen((open) => !open);
            setIsNotificationsOpen(false);
          }}
        >
          <span>{currentUser ? initialsForUser(currentUser) : <User aria-hidden="true" size={18} strokeWidth={1.9} />}</span>
          <ChevronDown aria-hidden="true" size={15} strokeWidth={1.9} />
        </button>

        {isAccountOpen ? (
          <div className="wiki-header-popover wiki-account-menu">
            {currentUser ? (
              <>
                <div className="wiki-account-menu-head">
                  <span className="wiki-account-avatar">{initialsForUser(currentUser)}</span>
                  <div>
                    <strong>{currentUser.username}</strong>
                    <small>{currentUser.email}</small>
                    <em className={`wiki-role-badge ${currentUser.role}`}>{roleLabel(currentUser.role)}</em>
                  </div>
                </div>
                <div className="wiki-account-menu-list">
                  <AccountMenuItem icon={User} onClick={() => navigate("/profile")}>Profile</AccountMenuItem>
                  {canOpenAdmin ? (
                    <AccountMenuItem icon={Gauge} onClick={() => navigate("/admin")}>
                      {isSuperadmin ? "Admin Dashboard" : "Editor Dashboard"}
                    </AccountMenuItem>
                  ) : null}
                  {isSuperadmin ? (
                    <>
                      <AccountMenuItem icon={UserCog} onClick={() => navigate("/admin/users")}>User Management</AccountMenuItem>
                      <AccountMenuItem icon={Settings} onClick={() => navigate("/admin/settings")}>System Settings</AccountMenuItem>
                    </>
                  ) : null}
                </div>
                <div className="wiki-account-menu-list separated">
                  <AccountMenuItem danger icon={LogOut} onClick={handleLogout}>Logout</AccountMenuItem>
                </div>
              </>
            ) : (
              <div className="wiki-account-menu-list">
                <AccountMenuItem icon={LogIn} onClick={() => navigate("/login")}>Sign In</AccountMenuItem>
                <AccountMenuItem icon={UserPlus} onClick={() => navigate("/register")}>Create Account</AccountMenuItem>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
