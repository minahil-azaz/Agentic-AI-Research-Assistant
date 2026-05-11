import { getToken, refreshAccessToken, clearTokens } from "./auth";

const BASE = "/api";

async function authFetch(url, options = {}) {
  let token = getToken();
  const headers = (t) => ({ "Content-Type": "application/json", ...options.headers, Authorization: `Bearer ${t}` });

  let res = await fetch(url, { ...options, headers: headers(token) });
  if (res.status === 401) {
    try {
      token = await refreshAccessToken();
      res   = await fetch(url, { ...options, headers: headers(token) });
    } catch {
      clearTokens();
      window.location.reload();
      throw new Error("Session expired.");
    }
  }
  return res;
}

export async function createResearch(query) {
  const res = await authFetch(`${BASE}/research/`, { method: "POST", body: JSON.stringify({ query }) });
  if (!res.ok) throw new Error(`Error: ${res.status}`);
  return res.json();
}

export function streamResearch(queryId, onEvent) {
  // EventSource cannot send headers — pass JWT as query param instead
  const token = getToken();
  const es    = new EventSource(`${BASE}/research/${queryId}/stream/?token=${encodeURIComponent(token)}`);

  es.onmessage = (e) => {
    try {
      const { type, ...data } = JSON.parse(e.data);
      onEvent(type, data);
    } catch {}
  };
  es.onerror = () => {
    onEvent("error", { message: "Stream disconnected. Check history for results." });
    es.close();
  };
  return () => es.close();
}

export async function listResearch() {
  const res = await authFetch(`${BASE}/research/list/`);
  if (!res.ok) throw new Error(`Error: ${res.status}`);
  return res.json();
}

export async function getResearch(id) {
  const res = await authFetch(`${BASE}/research/${id}/`);
  if (!res.ok) throw new Error(`Error: ${res.status}`);
  return res.json();
}

export async function deleteResearch(id) {
  const res = await authFetch(`${BASE}/research/${id}/`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Error: ${res.status}`);
}
