"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/lib/api";
import { hours } from "@/lib/format";
import { useAttempt, useIssue } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { nextStep, STATUS_LABEL } from "../attempts/progress";
import { Stepper } from "../attempts/Stepper";
import { Timeline } from "../attempts/Timeline";
import { ArrowLeftIcon, ExternalIcon } from "../ui/Icons";
import { EmptyState, ErrorNote, Skeleton } from "../ui/States";
import { useToast } from "../ui/Toast";

const TABS = ["Guide", "Code map", "Past PRs", "Timeline"] as const;
type Tab = (typeof TABS)[number];

function CopyBlock({ label, text, mono }: { label: string; text: string; mono?: boolean }) {
  const toast = useToast();
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted">{label}</span>
        <button
          onClick={async () => {
            await navigator.clipboard.writeText(text);
            toast({ message: "Copied" });
          }}
          className="rounded border border-border px-2 py-0.5 text-xs hover:bg-page"
        >
          Copy
        </button>
      </div>
      <pre className={`whitespace-pre-wrap rounded-lg bg-page p-3 text-sm ${mono ? "font-mono text-[13px]" : "font-sans"}`}>{text}</pre>
    </div>
  );
}

function ComingNext({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-dashed border-border p-8">
      <span className="self-start rounded-full bg-info-bg px-2 py-0.5 text-xs">Coming next</span>
      <p className="font-medium">{title}</p>
      <p className="max-w-xl text-sm text-ink-2">{body}</p>
    </div>
  );
}

export function WorkspaceView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const { owner, repo, number } = useParams<{ owner: string; repo: string; number: string }>();
  const issueId = `${owner}/${repo}#${number}`;
  const attempt = useAttempt(login, issueId);
  const issue = useIssue(login, issueId);
  const [tab, setTab] = useState<Tab>("Guide");

  const back = (
    <Link href="/trail" className="flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
      <ArrowLeftIcon className="h-4 w-4" /> My trail
    </Link>
  );

  if (attempt.error) {
    return (
      <>
        {back}
        {attempt.error instanceof ApiError && attempt.error.status === 404 ? (
          <EmptyState title="You haven't picked this issue" body={`${issueId} isn't on your trail yet.`} action={{ label: "Look at it", href: `/issues/${owner}/${repo}/${number}` }} />
        ) : (
          <ErrorNote message="Couldn't load this attempt." />
        )}
      </>
    );
  }
  if (!attempt.data) {
    return (
      <>
        {back}
        <Skeleton className="h-40" />
        <Skeleton className="h-80" />
      </>
    );
  }

  const a = attempt.data;
  const next = nextStep(a, number);
  const slug = `${owner}/${repo}`;
  const claim = `Hi! I'd like to work on this. My plan is to start by reproducing it, then put up a PR with a fix and a test.\n\nIs that OK, and is there anything I should know before I start? Thanks!`;
  const setup = `gh repo fork ${slug} --clone\ncd ${repo}\ngit checkout -b fix/issue-${number}`;
  const prHint = `Fixes #${number}\n\n## What\n<one line on the change>\n\n## How I tested it\n<commands you ran>`;

  return (
    <>
      {back}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-2">
          <span className="font-mono">{slug}</span>
          <span aria-hidden>·</span>
          <span>#{number}</span>
          <span aria-hidden>·</span>
          <span className="rounded-full bg-info-bg px-2 py-0.5 text-xs text-ink">{STATUS_LABEL[a.status]}</span>
          <a href={a.issue_url} target="_blank" rel="noreferrer" className="ml-auto flex items-center gap-1 hover:text-ink">
            Issue on GitHub <ExternalIcon className="h-4 w-4" />
          </a>
          {a.pr_url && (
            <a href={a.pr_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-ink">
              Your PR <ExternalIcon className="h-4 w-4" />
            </a>
          )}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{a.issue_title}</h1>
      </header>

      <section className="rounded-xl border border-border bg-surface p-6">
        <Stepper status={a.status} />
      </section>

      <section className="flex flex-col gap-1 rounded-xl border border-accent bg-info-bg p-5">
        <span className="text-xs font-medium uppercase tracking-wide text-accent-strong">Next step</span>
        <p className="text-lg font-medium">{next.title}</p>
        <p className="text-sm text-ink-2">{next.body}</p>
        {a.status === "merged" && (
          <Link href="/discover" className="mt-2 self-start rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white">
            Find a harder one →
          </Link>
        )}
        <p className="mt-2 text-xs text-muted">
          Progress here will update from your commits and PRs on GitHub automatically (coming next).
        </p>
      </section>

      <div className="flex gap-1 border-b border-border" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm ${tab === t ? "border-accent font-medium" : "border-transparent text-ink-2 hover:text-ink"}`}
          >
            {t}
            {t === "Timeline" && <span className="ml-1.5 text-xs text-muted">{a.events.length}</span>}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {tab === "Guide" && (
          <ol className="grid gap-6 lg:grid-cols-3">
            <li className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
              <p className="font-medium">1. Claim it</p>
              <CopyBlock label="Comment on the issue" text={claim} />
              <a href={a.issue_url} target="_blank" rel="noreferrer" className="text-sm text-accent-strong hover:underline">
                Open the issue to comment →
              </a>
            </li>
            <li className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
              <p className="font-medium">2. Set up</p>
              <CopyBlock label="Fork, clone and branch" text={setup} mono />
              <a href={`https://github.com/${slug}/blob/HEAD/CONTRIBUTING.md`} target="_blank" rel="noreferrer" className="text-sm text-accent-strong hover:underline">
                Read CONTRIBUTING.md, if it has one →
              </a>
            </li>
            <li className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
              <p className="font-medium">3. Open the PR</p>
              <CopyBlock label="PR description" text={prHint} />
              {issue.data && (
                <p className="text-xs text-ink-2">
                  Maintainers here usually reply within {hours(issue.data.repo.reply_hours)}; {issue.data.repo.newcomer_merges_90d} newcomer PRs merged
                  in the last 90 days.
                </p>
              )}
            </li>
          </ol>
        )}
        {tab === "Code map" && (
          <ComingNext
            title="A lit-up path through the code"
            body="We'll fetch just the files around this issue (no clone), map which functions call which, and highlight a reading order: where the code starts, the function to change, and its test."
          />
        )}
        {tab === "Past PRs" && (
          <ComingNext
            title="Merged PRs that touched the same code"
            body="Worked examples from this repo: who changed these files before, how they did it, and how quickly they got reviewed."
          />
        )}
        {tab === "Timeline" && (
          <div className="rounded-xl border border-border bg-surface p-6">
            <Timeline events={a.events} />
          </div>
        )}
      </div>
    </>
  );
}
