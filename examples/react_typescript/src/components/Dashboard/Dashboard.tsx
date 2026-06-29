import React, { useState } from "react";
import { useItems } from "../../hooks/useApi";
import type { User } from "../../types";

interface Props {
  user: User;
  token: string;
  onLogout: () => void;
}

export function Dashboard({ user, token, onLogout }: Props): React.JSX.Element {
  const { items, isLoading, error, createItem, deleteItem } = useItems(token);
  const [newTitle, setNewTitle] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await createItem(newTitle);
    setNewTitle("");
  };

  return (
    <main>
      <header>
        <h1>Dashboard</h1>
        <span>Logged in as <strong>{user.username}</strong></span>
        <button onClick={onLogout}>Sign out</button>
      </header>

      <section aria-label="Create item">
        <form onSubmit={handleCreate}>
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="New item title…"
            aria-label="Item title"
          />
          <button type="submit">Add</button>
        </form>
      </section>

      <section aria-label="Items">
        {isLoading && <p>Loading…</p>}
        {error && <p role="alert">{error}</p>}
        <ul>
          {items.map((item) => (
            <li key={item.id}>
              <span>{item.title}</span>
              <button onClick={() => deleteItem(item.id)} aria-label={`Delete ${item.title}`}>
                ×
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
