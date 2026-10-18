"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ApiError, issuePath } from "@/lib/api";
import { useIssue } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { IssueSummary } from "../issues/IssueSummary";
import { ArrowLeftIcon } from "../ui/Icons";
import { ErrorNote, Skeleton } from "../ui/States";

function hours(h: number | null) {
  if (h === null) return "unknown";
  return h < 1 ? "under an hour" : h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)} days`;
}

export function IssueView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const issueId = `${owner}/${repo}#${number}`;
  const { data, error } = useIssue(login, issueId);

  const back = (
    <Link href="/discover" className="flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
      <ArrowLeftIcon className="h-4 w-4" /> Discover
    </Link>
  );

  if (error) {
    return (
      <>
        {back}
        <ErrorNote message={error instanceof ApiError && error.status === 404 ? `${issueId} doesn't exist or isn't an issue.` : "Couldn't load this issue."} />
      </>
    );
  }
  if (!data) {
    return (
      <>
        {back}
        <p className="text-sm text-ink-2">Scoring {issueId} for you: checking claims and how the maintainers respond…</p>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-[30rem]" />
          <Skeleton className="h-[30rem]" />
        </div>
      </>
    );
  }

  const { card, repo: health } = data;
  const newcomerTotal = health.newcomer_merged + health.newcomer_closed;

  return (
    <>
      {back}
      {data.attempt_id && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-info-bg p-3 text-sm">
          This issue is on your trail.
          <Link href={`/trail/${issuePath(card.id)}`} className="font-medium text-accent-strong hover:underline">
            Open workspace →
          </Link>
        </div>
      )}
      {data.stale && <ErrorNote message="GitHub isn't responding, so some of this may be out of date." />}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <section className="rounded-xl border border-border bg-surface p-6">
          <IssueSummary login={login} card={card} standalone />
        </section>

        <div className="flex flex-col gap-6">
          <section className="rounded-xl border border-border bg-surface p-6">
            <h2 className="mb-3 text-sm font-medium">How {health.repo} treats newcomers</h2>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-xs text-muted">Maintainers first reply</dt>
                <dd className="text-lg font-medium">{hours(health.reply_hours)}</dd>
                <dd className="text-xs text-muted">median, recent PRs</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Newcomer PRs merged</dt>
                <dd className="text-lg font-medium">{health.newcomer_merges_90d}</dd>
                <dd className="text-xs text-muted">last 90 days</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Newcomer merge rate</dt>
                <dd className="text-lg font-medium">{newcomerTotal ? `${Math.round((health.newcomer_merged / newcomerTotal) * 100)}%` : "—"}</dd>
                <dd className="text-xs text-muted">
                  {health.newcomer_merged} of {newcomerTotal} recent newcomer PRs
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Stars</dt>
                <dd className="text-lg font-medium">{health.stars.toLocaleString()}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-xl border border-border bg-surface p-6">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-sm font-medium">From the issue</h2>
              <span className="text-xs text-muted">
                {data.comments} comment{data.comments === 1 ? "" : "s"}
                {data.claimed_by && ` · claimed by @${data.claimed_by}`}
              </span>
            </div>
            <div className="markdown max-h-[32rem] overflow-y-auto text-sm">
              {data.body.trim() ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.body}</ReactMarkdown> : <p className="text-ink-2">No description.</p>}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
