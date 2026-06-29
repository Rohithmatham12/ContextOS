import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Item } from "../types";

export function useItems(token: string | null): {
  items: Item[];
  isLoading: boolean;
  error: string | null;
  createItem: (title: string, description?: string) => Promise<void>;
  deleteItem: (id: number) => Promise<void>;
  refresh: () => void;
} {
  const [items, setItems] = useState<Item[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(() => {
    if (!token) return;
    setLoading(true);
    api
      .getItems(token)
      .then((data) => { setItems(data); setLoading(false); })
      .catch((err: Error) => { setError(err.message); setLoading(false); });
  }, [token]);

  useEffect(() => { fetch(); }, [fetch]);

  const createItem = useCallback(
    async (title: string, description = "") => {
      if (!token) return;
      const item = await api.createItem(token, title, description);
      setItems((prev) => [...prev, item]);
    },
    [token]
  );

  const deleteItem = useCallback(
    async (id: number) => {
      if (!token) return;
      await api.deleteItem(token, id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    },
    [token]
  );

  return { items, isLoading, error, createItem, deleteItem, refresh: fetch };
}
