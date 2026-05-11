const BASE = "/api/auth";

export const getToken   = () => localStorage.getItem("access_token");
export const getRefresh = () => localStorage.getItem("refresh_token");
export const getUser    = () => { try { return JSON.parse(localStorage.getItem("user")); } catch { return null; } };

export function saveTokens(access, refresh) {
  localStorage.setItem("access_token", access);
  if (refresh) localStorage.setItem("refresh_token", refresh);
}
export function saveUser(user) {
  localStorage.setItem("user", JSON.stringify(user));
}
export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

export async function register({ username, email, password, password2 }) {
  const res  = await fetch(`${BASE}/register/`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ username, email, password, password2 }),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  saveTokens(data.access, data.refresh);
  saveUser(data.user);
  return data;
}

export async function login({ username, password }) {
  const res  = await fetch(`${BASE}/login/`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  saveTokens(data.access, data.refresh);
  saveUser(data.user);
  return data;
}

export async function logout() {
  const refresh = getRefresh();
  const token   = getToken();
  try {
    await fetch(`${BASE}/logout/`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body:    JSON.stringify({ refresh }),
    });
  } catch {}
  clearTokens();
}

export async function refreshAccessToken() {
  const refresh = getRefresh();
  if (!refresh) throw new Error("No refresh token");
  const res  = await fetch(`${BASE}/token/refresh/`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ refresh }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error("Refresh failed");
  saveTokens(data.access, data.refresh);
  return data.access;
}
