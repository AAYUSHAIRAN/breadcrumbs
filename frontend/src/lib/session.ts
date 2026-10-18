"use client";

import { useSyncExternalStore } from "react";

// No auth for the hackathon: we remember which GitHub user you are in localStorage.
const KEY = "breadcrumbs.login";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function setLogin(login: string | null) {
  if (login) localStorage.setItem(KEY, login);
  else localStorage.removeItem(KEY);
  listeners.forEach((l) => l());
}

/** The remembered login; `undefined` while rendering on the server (not known yet). */
export function useLogin(): string | null | undefined {
  return useSyncExternalStore(
    subscribe,
    () => localStorage.getItem(KEY),
    () => undefined,
  );
}
