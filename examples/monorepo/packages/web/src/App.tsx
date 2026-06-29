import React, { useEffect, useState } from "react";
import type { Project, User } from "@example/shared/src/types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:4000";

async function apiFetch<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export default function App(): React.JSX.Element {
  const [user] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ data: Project[] }>("/projects")
      .then((r) => { setProjects(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <main>
      <h1>Projects</h1>
      {loading && <p>Loading…</p>}
      {!loading && projects.length === 0 && <p>No projects yet.</p>}
      <ul>
        {projects.map((p) => (
          <li key={p.id}>
            <strong>{p.name}</strong> — {p.members.length} member(s)
          </li>
        ))}
      </ul>
      {!user && <a href="/login">Sign in</a>}
    </main>
  );
}
