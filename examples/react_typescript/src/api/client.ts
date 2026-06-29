import type { Item, User } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) => {
    const body = new URLSearchParams({ username, password });
    return fetch(`${BASE_URL}/users/token`, { method: "POST", body }).then(
      (r) => r.json() as Promise<{ access_token: string; token_type: string }>
    );
  },

  me: (token: string) => request<User>("/users/me", {}, token),

  getItems: (token: string) => request<Item[]>("/items/", {}, token),

  createItem: (token: string, title: string, description = "") =>
    request<Item>("/items/", { method: "POST", body: JSON.stringify({ title, description }) }, token),

  deleteItem: (token: string, id: number) =>
    request<void>(`/items/${id}`, { method: "DELETE" }, token),
};
