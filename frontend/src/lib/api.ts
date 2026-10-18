import type { Attempt, Fingerprint, Matches, SkipRequest } from "./contracts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `API error ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body.detail ?? body);
  }
  return resp.status === 204 ? (undefined as T) : resp.json();
}

const user = (login: string) => `/users/${encodeURIComponent(login)}`;

export const api = {
  fingerprint: (login: string) => request<Fingerprint>(`${user(login)}/fingerprint`),
  matches: (login: string) => request<Matches>(`${user(login)}/matches`),
  attempts: (login: string) => request<Attempt[]>(`${user(login)}/attempts`),
  pick: (login: string, issueId: string, force = false) =>
    request<Attempt>(`${user(login)}/attempts`, {
      method: "POST",
      body: JSON.stringify({ issue_id: issueId, force }),
    }),
  skip: (login: string, issueId: string, reason: SkipRequest["reason"]) => {
    const [repo, number] = issueId.split("#");
    return request<void>(`${user(login)}/issues/${repo}/${number}/skip`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },
};

/** The 409 body from POST /attempts when the issue was taken since it was shown. */
export interface Unavailable {
  issue_id: string;
  reason: "closed" | "assigned" | "pr_open" | "claimed" | "not_found";
  message: string;
  detail_url: string | null;
}
