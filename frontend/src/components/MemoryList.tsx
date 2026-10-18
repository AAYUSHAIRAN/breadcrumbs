"use client";

import useSWR from "swr";

import { api } from "@/lib/api";
import { useToast } from "./ui/Toast";

/** What the Guide agent remembers about the user, from the graph. Deletable. */
export function MemoryList({ login }: { login: string }) {
  const toast = useToast();
  const { data, mutate } = useSWR(login ? ["memory", login] : null, () => api.memory(login), { revalidateOnFocus: false });
  const items = data?.memories ?? [];
  return (
    <section className="rounded-xl border border-border bg-surface p-6">
      <h2 className="font-medium">What Guide remembers about you</h2>
      <p className="mb-3 text-sm text-ink-2">
        Notes the agent saved to your graph (<span className="font-mono text-xs">(User)-[:REMEMBERS]-&gt;(Memory)</span>). It reads them
        every time it writes for you.
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing yet. Run ✨ Write with Guide in an issue&apos;s workspace.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((m) => (
            <li key={m.id} className="flex items-start justify-between gap-3 rounded-lg bg-page px-3 py-2 text-sm">
              <span>{m.text}</span>
              <button
                onClick={async () => {
                  await api.forget(login, m.id);
                  await mutate();
                  toast({ message: "Forgotten" });
                }}
                className="text-xs text-ink-2 hover:text-ink"
                aria-label={`Forget: ${m.text}`}
              >
                Forget
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
