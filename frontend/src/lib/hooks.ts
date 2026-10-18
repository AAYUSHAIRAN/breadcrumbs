"use client";

import useSWR from "swr";

import { api } from "./api";

// SWR keeps responses across page navigations, so moving between screens is instant.
const options = { revalidateOnFocus: false, shouldRetryOnError: false };
type Login = string | null | undefined;

/** Fetch once we know who the user is (and any other key parts are set). */
function useKeyed<T>(login: Login, key: (string | null)[], fetch: (login: string) => Promise<T>) {
  const ready = login && key.every((k) => k !== null);
  return useSWR(ready ? [...key, login] : null, () => fetch(login!), options);
}

export const useFingerprint = (login: Login) => useKeyed(login, ["fingerprint"], api.fingerprint);
export const useMatches = (login: Login) => useKeyed(login, ["matches"], api.matches);
export const useAttempts = (login: Login) => useKeyed(login, ["attempts"], api.attempts);
export const useSaved = (login: Login) => useKeyed(login, ["saved"], api.saved);
export const useTrailGraph = (login: Login) => useKeyed(login, ["trail-graph"], api.trailGraph);

export const useIssue = (login: Login, issueId: string | null) =>
  useKeyed(login, ["issue", issueId], (l) => api.issue(l, issueId!));
/** The why-graph needs the issue in the graph first, so wait until the issue has loaded (`ready`). */
export const useWhy = (login: Login, issueId: string | null, ready: boolean) =>
  useKeyed(login, ["why", ready ? issueId : null], (l) => api.why(l, issueId!));
export const useAttempt = (login: Login, issueId: string | null) =>
  useKeyed(login, ["attempt", issueId], (l) => api.attempt(l, issueId!));
