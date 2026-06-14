import React from "react";
import { BookOpen, KeyRound, LogIn, Save, UserPlus } from "lucide-react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";

export function WikiLoginPage() {
  const { currentUser, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  if (currentUser) {
    return <Navigate to="/wiki/novels" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate("/wiki/novels", { replace: true });
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="wiki-auth-page">
      <form className="wiki-auth-card" onSubmit={handleSubmit}>
        <div className="wiki-auth-mark">
          <LogIn aria-hidden="true" size={28} strokeWidth={1.9} />
        </div>
        <div>
          <h1>Sign In</h1>
          <p>Access your wiki account, bookmarks, and admin tools if assigned.</p>
        </div>
        {error ? <div className="wiki-auth-error">{error}</div> : null}
        <label>
          Email
          <input
            autoComplete="email"
            autoFocus
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
          />
        </label>
        <button disabled={isSubmitting} type="submit">
          <LogIn aria-hidden="true" size={17} strokeWidth={1.9} />
          {isSubmitting ? "Signing in..." : "Sign In"}
        </button>
        <p className="wiki-auth-switch">
          No account yet? <Link to="/register">Create Account</Link>
        </p>
      </form>
    </main>
  );
}

export function WikiRegisterPage() {
  const { currentUser, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = React.useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  if (currentUser) {
    return <Navigate to="/wiki/novels" replace />;
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await fetchJson(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          password: form.password,
        }),
      });
      await login(form.email, form.password);
      navigate("/wiki/novels", { replace: true });
    } catch (registerError) {
      setError(registerError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="wiki-auth-page">
      <form className="wiki-auth-card" onSubmit={handleSubmit}>
        <div className="wiki-auth-mark">
          <UserPlus aria-hidden="true" size={28} strokeWidth={1.9} />
        </div>
        <div>
          <h1>Create Account</h1>
          <p>Public accounts can browse the wiki. Admin roles are assigned separately.</p>
        </div>
        {error ? <div className="wiki-auth-error">{error}</div> : null}
        <label>
          Username
          <input
            autoComplete="username"
            autoFocus
            value={form.username}
            onChange={(event) => updateField("username", event.target.value)}
            placeholder="David Tabidze"
          />
        </label>
        <label>
          Email
          <input
            autoComplete="email"
            type="email"
            value={form.email}
            onChange={(event) => updateField("email", event.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Password
          <input
            autoComplete="new-password"
            type="password"
            value={form.password}
            onChange={(event) => updateField("password", event.target.value)}
            placeholder="At least 8 characters"
          />
        </label>
        <label>
          Confirm Password
          <input
            autoComplete="new-password"
            type="password"
            value={form.confirmPassword}
            onChange={(event) => updateField("confirmPassword", event.target.value)}
            placeholder="Repeat password"
          />
        </label>
        <button disabled={isSubmitting} type="submit">
          <UserPlus aria-hidden="true" size={17} strokeWidth={1.9} />
          {isSubmitting ? "Creating account..." : "Create Account"}
        </button>
        <p className="wiki-auth-switch">
          Already have an account? <Link to="/login">Sign In</Link>
        </p>
      </form>
    </main>
  );
}

export function WikiSetPasswordPage() {
  const { currentUser } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [tokenInfo, setTokenInfo] = React.useState(null);
  const [error, setError] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!token) {
      setError("Password setup token is missing.");
      return;
    }

    fetchJson(`${API_BASE_URL}/auth/password-setup?token=${encodeURIComponent(token)}`)
      .then(setTokenInfo)
      .catch((setupError) => setError(setupError.message));
  }, [token]);

  if (currentUser) {
    return <Navigate to="/wiki/novels" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await fetchJson(`${API_BASE_URL}/auth/set-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          confirm_password: confirmPassword,
        }),
      });
      navigate("/login", { replace: true });
    } catch (setupError) {
      setError(setupError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="wiki-auth-page">
      <form className="wiki-auth-card" onSubmit={handleSubmit}>
        <div className="wiki-auth-mark">
          <KeyRound aria-hidden="true" size={28} strokeWidth={1.9} />
        </div>
        <div>
          <h1>Set Password</h1>
          <p>
            {tokenInfo?.user
              ? `Create a password for ${tokenInfo.user.email}.`
              : "Create a password for your wiki account."}
          </p>
        </div>
        {error ? <div className="wiki-auth-error">{error}</div> : null}
        <label>
          New Password
          <input
            autoComplete="new-password"
            autoFocus
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="At least 8 characters"
          />
        </label>
        <label>
          Confirm Password
          <input
            autoComplete="new-password"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Repeat password"
          />
        </label>
        <button disabled={isSubmitting || !token || Boolean(error && !tokenInfo)} type="submit">
          <KeyRound aria-hidden="true" size={17} strokeWidth={1.9} />
          {isSubmitting ? "Saving password..." : "Set Password"}
        </button>
        <p className="wiki-auth-switch">
          Already set your password? <Link to="/login">Sign In</Link>
        </p>
      </form>
    </main>
  );
}

export function WikiProfilePage() {
  const { currentUser, refreshCurrentUser } = useAuth();
  const [displayName, setDisplayName] = React.useState(currentUser?.username || "");
  const [passwordForm, setPasswordForm] = React.useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    setDisplayName(currentUser?.username || "");
  }, [currentUser?.username]);

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  async function saveProfile(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    try {
      await fetchJson(`${API_BASE_URL}/auth/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: displayName }),
      });
      await refreshCurrentUser();
      setMessage("Profile updated.");
    } catch (profileError) {
      setError(profileError.message);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    try {
      await fetchJson(`${API_BASE_URL}/auth/me/password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: passwordForm.currentPassword,
          new_password: passwordForm.newPassword,
          confirm_password: passwordForm.confirmPassword,
        }),
      });
      setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setMessage("Password changed.");
    } catch (passwordError) {
      setError(passwordError.message);
    }
  }

  return (
    <main className="wiki-auth-page">
      <section className="wiki-auth-card wiki-profile-card wide">
        <div className="wiki-auth-mark">
          <BookOpen aria-hidden="true" size={28} strokeWidth={1.9} />
        </div>
        <div>
          <h1>Profile</h1>
          <p>Your public wiki account details and password settings.</p>
        </div>
        {message ? <div className="wiki-auth-success">{message}</div> : null}
        {error ? <div className="wiki-auth-error">{error}</div> : null}
        <dl className="wiki-profile-list">
          <div>
            <dt>Email</dt>
            <dd>{currentUser.email}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{currentUser.role}</dd>
          </div>
        </dl>
        <form className="wiki-profile-form" onSubmit={saveProfile}>
          <label>
            Display Name
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <button type="submit">
            <Save aria-hidden="true" size={17} strokeWidth={1.9} />
            Save Profile
          </button>
        </form>
        <form className="wiki-profile-form" onSubmit={changePassword}>
          <label>
            Current Password
            <input
              autoComplete="current-password"
              type="password"
              value={passwordForm.currentPassword}
              onChange={(event) => setPasswordForm((current) => ({ ...current, currentPassword: event.target.value }))}
            />
          </label>
          <label>
            New Password
            <input
              autoComplete="new-password"
              type="password"
              value={passwordForm.newPassword}
              onChange={(event) => setPasswordForm((current) => ({ ...current, newPassword: event.target.value }))}
            />
          </label>
          <label>
            Confirm New Password
            <input
              autoComplete="new-password"
              type="password"
              value={passwordForm.confirmPassword}
              onChange={(event) => setPasswordForm((current) => ({ ...current, confirmPassword: event.target.value }))}
            />
          </label>
          <button type="submit">
            <KeyRound aria-hidden="true" size={17} strokeWidth={1.9} />
            Change Password
          </button>
        </form>
        <Link className="wiki-auth-link-button" to="/wiki/novels">Back to Wiki</Link>
      </section>
    </main>
  );
}
