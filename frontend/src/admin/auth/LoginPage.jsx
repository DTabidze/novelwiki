import React from "react";
import { LogIn } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext.jsx";

export default function LoginPage() {
  const { currentUser, isAuthLoading, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const redirectTo = location.state?.from?.pathname || "/admin/novels";

  if (!isAuthLoading && currentUser?.role && currentUser.role !== "user") {
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const user = await login(email, password);

      if (user.role === "user") {
        setError("This account does not have admin access.");
        return;
      }

      navigate(redirectTo, { replace: true });
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="admin-login-shell">
      <form className="admin-login-card" onSubmit={handleSubmit}>
        <div className="admin-login-mark">
          <LogIn aria-hidden="true" size={28} strokeWidth={1.9} />
        </div>
        <div>
          <h1>Admin Login</h1>
          <p>Sign in to manage extraction, review, and canonical wiki data.</p>
        </div>

        {error ? <div className="admin-message danger">{error}</div> : null}

        <label>
          Email
          <input
            autoComplete="email"
            autoFocus
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@example.com"
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
      </form>
    </main>
  );
}
