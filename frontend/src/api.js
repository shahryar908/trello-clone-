const BASE_URL = "http://localhost:8000";
export const WS_BASE = "ws://localhost:8000";

export function getToken() {
  return localStorage.getItem("token");
}

export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(BASE_URL + path, { ...options, headers });

  // expired/invalid session — but never redirect for the login/signup calls themselves
  if (res.status === 401 && !path.startsWith("/auth")) {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.detail) || `Request failed (${res.status})`);
  }
  return data;
}
