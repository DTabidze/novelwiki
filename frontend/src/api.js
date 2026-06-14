const API_HOST = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `http://${API_HOST}:5050/api`;

let csrfToken = null;

export function setCsrfToken(token) {
  csrfToken = token || null;
}

async function ensureCsrfToken() {
  if (csrfToken) {
    return csrfToken;
  }

  const response = await fetch(`${API_BASE_URL}/auth/csrf`, {
    credentials: "include",
  });
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Could not fetch CSRF token");
  }

  csrfToken = body.data?.csrf_token || null;
  return csrfToken;
}

export async function fetchJson(url, options) {
  const requestOptions = {
    ...(options || {}),
    credentials: "include",
  };
  const method = (requestOptions.method || "GET").toUpperCase();

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = await ensureCsrfToken();
    requestOptions.headers = {
      ...(requestOptions.headers || {}),
      "X-CSRF-Token": token,
    };
  }

  const response = await fetch(url, requestOptions);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }

  return body.data;
}
