"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function UsernameForm() {
  const router = useRouter();
  const [login, setLogin] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const clean = login.trim().replace(/^@/, "");
    if (clean) router.push(`/u/${encodeURIComponent(clean)}`);
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-md gap-2">
      <label htmlFor="login" className="sr-only">
        GitHub username
      </label>
      <input
        id="login"
        value={login}
        onChange={(e) => setLogin(e.target.value)}
        placeholder="your GitHub username"
        autoComplete="off"
        autoFocus
        className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-ink placeholder:text-muted focus:outline-2 focus:outline-accent"
      />
      <button
        type="submit"
        disabled={!login.trim()}
        className="rounded-lg bg-accent-strong px-5 py-3 font-medium text-white disabled:opacity-40"
      >
        Find issues
      </button>
    </form>
  );
}
