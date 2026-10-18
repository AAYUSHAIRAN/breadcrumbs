"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { issuePath } from "@/lib/api";
import { ago, greeting } from "@/lib/format";
import { useAttempts, useFingerprint, useMatches, useSaved } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { isActive, nextStep, STATUS_LABEL } from "../attempts/progress";
import { Stepper } from "../attempts/Stepper";
import { IssueRow } from "../issues/IssueRow";
import { EmptyState, Skeleton } from "../ui/States";

function Stat({ label, value }: { label: string; value: number | string | undefined }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold tracking-tight">{value ?? "–"}</dd>
    </div>
  );
}

export function HomeView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const router = useRouter();
  const user = useFingerprint(login);
  const attempts = useAttempts(login);
  const matches = useMatches(login);
  const saved = useSaved(login);

  const all = attempts.data ?? [];
  const active = all.filter(isActive);
  const current = active[0];
  const prs = all.filter((a) => ["pr_open", "in_review", "changes_requested"].includes(a.status)).length;

  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          {greeting()}
          {user.data ? `, ${user.data.name?.split(" ")[0] ?? user.data.login}` : ""}
        </h1>
        <p className="mt-1 text-sm text-ink-2">{current ? "Pick up where you left off." : "Let's find your next contribution."}</p>
      </header>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="In progress" value={attempts.data && active.length} />
        <Stat label="PRs open" value={attempts.data && prs} />
        <Stat label="Merged" value={attempts.data && all.filter((a) => a.status === "merged").length} />
        <Stat label="Saved" value={saved.data?.length} />
      </dl>

      {!attempts.data ? (
        <Skeleton className="h-48" />
      ) : current ? (
        <section className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <p className="text-xs text-muted">
                Continue · {STATUS_LABEL[current.status]} · active {ago(current.last_activity_at)}
              </p>
              <p className="mt-1 text-lg font-medium">{current.issue_title}</p>
              <p className="font-mono text-xs text-ink-2">{current.issue_id}</p>
            </div>
            <Link href={`/trail/${issuePath(current.issue_id)}`} className="rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white">
              Open workspace →
            </Link>
          </div>
          <Stepper status={current.status} />
          <p className="text-sm">
            <span className="font-medium">Next: {nextStep(current, current.issue_id.split("#")[1]).title}.</span>{" "}
            <span className="text-ink-2">{nextStep(current, current.issue_id.split("#")[1]).body}</span>
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-info-bg p-4 text-sm">
            <span>
              <span className="font-medium">✨ Guide, our AI agent,</span>{" "}
              <span className="text-ink-2">can write your claim comment, setup commands and PR for this repo, following its own rules.</span>
            </span>
            <Link href={`/trail/${issuePath(current.issue_id)}`} className="font-medium text-accent-strong hover:underline">
              Open Guide →
            </Link>
          </div>
        </section>
      ) : (
        <EmptyState title="No issue in progress" body="Pick an issue that fits you, and Guide, our AI agent, will write your claim comment, setup steps and PR." action={{ label: "Discover issues", href: "/discover" }} />
      )}

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h2 className="font-medium">Top picks for you</h2>
          <Link href="/discover" className="text-sm text-accent-strong hover:underline">
            See all →
          </Link>
        </div>
        {matches.data ? (
          matches.data.issues.length ? (
            <ul className="grid gap-2 md:grid-cols-3">
              {matches.data.issues.slice(0, 3).map((card) => (
                <li key={card.id}>
                  <IssueRow card={card} onSelect={() => router.push(`/issues/${issuePath(card.id)}`)} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-2">No good matches right now.</p>
          )
        ) : (
          <div className="grid gap-2 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
