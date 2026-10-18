"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { Attempt, AttemptStatus, Fingerprint, Matches } from "@/lib/contracts";
import { IssueCard } from "./IssueCard";
import { SkillBars } from "./SkillBars";

// Shown while the first (uncached) match takes a few seconds. These are the real steps.
const WORKING = [
  "Finding active projects in your languages…",
  "Looking at the libraries you depend on…",
  "Checking who has already claimed what…",
  "Measuring how fast maintainers reply…",
];

const STATUS_LABEL: Record<AttemptStatus, string> = {
  selected: "picked",
  in_progress: "in progress",
  pr_open: "PR open",
  in_review: "in review",
  changes_requested: "changes requested",
  merged: "merged 🎉",
  closed: "closed",
  abandoned: "abandoned",
};

function errorMessage(e: unknown) {
  if (e instanceof ApiError && e.status === 404) return "That GitHub user doesn't exist.";
  if (e instanceof TypeError) return "Can't reach the Breadcrumbs API. Is the backend running (make api)?";
  return e instanceof Error ? e.message : "Something went wrong.";
}

export function UserView() {
  const { login } = useParams<{ login: string }>();
  const [user, setUser] = useState<Fingerprint | null>(null);
  const [matches, setMatches] = useState<Matches | null>(null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const fp = await api.fingerprint(login);
        if (cancelled) return;
        setUser(fp);
        const [m, a] = await Promise.all([api.matches(fp.login), api.attempts(fp.login)]);
        if (cancelled) return;
        setMatches(m);
        setAttempts(a);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [login]);

  useEffect(() => {
    if (matches) return;
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, WORKING.length - 1)), 2500);
    return () => clearInterval(timer);
  }, [matches]);

  function removeCard(id: string) {
    setMatches((m) => m && { ...m, issues: m.issues.filter((i) => i.id !== id) });
  }

  if (error) {
    return (
      <main className="mx-auto w-full max-w-5xl px-6 py-16">
        <p role="alert" className="rounded-lg bg-warn-bg p-4 text-warn">
          ⚠ {error}
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto grid w-full max-w-5xl gap-8 px-6 py-10 lg:grid-cols-[18rem_1fr]">
      <aside className="flex flex-col gap-6">
        <Link href="/" className="font-mono text-sm text-muted hover:text-ink">
          ← breadcrumbs
        </Link>
        {user ? (
          <>
            <div className="flex items-center gap-3">
              {user.avatar_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar_url} alt="" className="h-12 w-12 rounded-full" />
              )}
              <div>
                <p className="font-medium">{user.name ?? user.login}</p>
                <p className="font-mono text-sm text-ink-2">@{user.login}</p>
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border bg-surface p-3">
                <dt className="text-xs text-muted">Level</dt>
                <dd className="font-medium capitalize">{user.level}</dd>
              </div>
              <div className="rounded-lg border border-border bg-surface p-3">
                <dt className="text-xs text-muted">Merged PRs</dt>
                <dd className="font-medium">{user.merged_prs}</dd>
              </div>
            </dl>
            <section className="flex flex-col gap-2">
              <h2 className="text-sm font-medium">Skills</h2>
              <SkillBars skills={user.skills} />
            </section>
          </>
        ) : (
          <p className="text-sm text-ink-2">Reading @{login}&apos;s public repos…</p>
        )}

        {attempts.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-medium">Your trail</h2>
            <ul className="flex flex-col gap-2">
              {attempts.map((a) => (
                <li key={a.id} className="rounded-lg border border-border bg-surface p-3 text-sm">
                  <a href={a.issue_url} target="_blank" rel="noreferrer" className="hover:underline">
                    {a.issue_title}
                  </a>
                  <p className="mt-1 font-mono text-xs text-ink-2">
                    {a.issue_id} · {STATUS_LABEL[a.status]}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>

      <section className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Issues you can land</h1>
          <p className="text-sm text-ink-2">
            Unclaimed, recently active, in repos where maintainers reply and newcomers get merged.
          </p>
        </div>
        {matches?.stale && (
          <p className="rounded-lg bg-warn-bg p-3 text-sm text-warn">
            ⚠ GitHub isn&apos;t responding, so some of this may be out of date.
          </p>
        )}
        {!matches && user && (
          <div className="flex flex-col gap-3" aria-live="polite">
            <p className="text-sm text-ink-2">{WORKING[step]}</p>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-44 animate-pulse rounded-xl border border-border bg-surface" />
            ))}
          </div>
        )}
        {matches && matches.issues.length === 0 && (
          <p className="text-ink-2">No good matches right now. Try again later: new issues show up every day.</p>
        )}
        {matches?.issues.map((card) => (
          <IssueCard
            key={card.id}
            login={matches.login}
            card={card}
            onPicked={(a) => {
              setAttempts((prev) => [a, ...prev.filter((p) => p.id !== a.id)]);
              removeCard(card.id);
            }}
            onSkipped={() => removeCard(card.id)}
          />
        ))}
      </section>
    </main>
  );
}
