export const API_BASE_URL = "http://127.0.0.1:5050/api";

export async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }

  return body.data;
}
