"use client";

import { useState } from "react";

import { ApiError, type Unavailable, api } from "@/lib/api";
import type { Attempt, IssueCard as Card, SkipRequest, WhyChip } from "@/lib/contracts";
import { Meter } from "./Meter";

const CHIP_STYLE: Record<WhyChip["kind"], { cls: string; icon: string }> = {
  skill: { cls: "bg-info-bg text-ink", icon: "" },
  dependency: { cls: "bg-info-bg text-ink", icon: "" },
  unclaimed: { cls: "bg-good-bg text-good", icon: "✓ " },
  fast_maintainer: { cls: "bg-good-bg text-good", icon: "✓ " },
  newcomers: { cls: "bg-good-bg text-good", icon: "✓ " },
  small_scope: { cls: "bg-good-bg text-good", icon: "✓ " },
  warning: { cls: "bg-warn-bg text-warn", icon: "⚠ " },
};

const SKIP_REASONS: [SkipRequest["reason"], string][] = [
  ["not_interested", "Not interested"],
  ["too_hard", "Too hard"],
  ["too_easy", "Too easy"],
  ["wrong_tech", "Wrong tech"],
];

function hours(h: number | null) {
  if (h === null) return "unknown";
  if (h < 1) return "under an hour";
  return h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)} days`;
}

export function IssueCard({
  login,
  card,
  onPicked,
  onSkipped,
}: {
  login: string;
  card: Card;
  onPicked: (attempt: Attempt) => void;
  onSkipped: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [taken, setTaken] = useState<Unavailable | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(force = false) {
    setBusy(true);
    setError(null);
    try {
      onPicked(await api.pick(login, card.id, force));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setTaken(e.detail as Unavailable);
      else setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function skip(reason: SkipRequest["reason"]) {
    setBusy(true);
    try {
      await api.skip(login, card.id, reason);
      onSkipped();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBusy(false);
    }
  }

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5">
      <header className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">
          <span className="font-mono">{card.repo}</span>
          <span aria-hidden>·</span>
          <span>★ {card.repo_stars.toLocaleString()}</span>
          <span aria-hidden>·</span>
          <span className="rounded border border-border px-1.5 py-0.5">{card.difficulty}</span>
          {card.in_dependencies && <span className="rounded bg-info-bg px-1.5 py-0.5">📦 your dependency</span>}
        </div>
        <h2 className="text-lg font-medium leading-snug">
          <a href={card.url} target="_blank" rel="noreferrer" className="hover:underline">
            {card.title}
          </a>
          <span className="ml-2 font-mono text-sm text-muted">#{card.number}</span>
        </h2>
      </header>

      <ul className="flex flex-wrap gap-1.5" aria-label="Why this issue">
        {card.why.map((w) => (
          <li key={w.label} className={`rounded-full px-2.5 py-1 text-xs ${CHIP_STYLE[w.kind].cls}`}>
            {CHIP_STYLE[w.kind].icon}
            {w.label}
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-2 gap-4">
        <Meter label="Fit" value={card.fit} hint="Skill match, difficulty for your level, maintainer speed, newcomer merges, freshness" />
        <Meter
          label="Merge chance"
          value={card.merge_forecast}
          hint="Rough estimate from how often newcomer PRs get merged here, issue difficulty and maintainer speed"
        />
      </div>

      {open && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-page p-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted">Maintainers reply</dt>
            <dd>{hours(card.maintainer_reply_hours)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Newcomer merges (90d)</dt>
            <dd>{card.newcomer_merges_90d}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Last activity</dt>
            <dd>{new Date(card.updated_at).toLocaleDateString()}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Claimed</dt>
            <dd>{card.claimed ? "yes" : "no"}</dd>
          </div>
          <div className="col-span-full">
            <dt className="text-xs text-muted">Labels</dt>
            <dd className="flex flex-wrap gap-1 pt-1">
              {card.labels.map((l) => (
                <span key={l} className="rounded border border-border px-1.5 py-0.5 text-xs">
                  {l}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      )}

      {taken && (
        <div role="alert" className="rounded-lg bg-warn-bg p-3 text-sm text-warn">
          ⚠ {taken.message}{" "}
          {taken.detail_url && (
            <a href={taken.detail_url} target="_blank" rel="noreferrer" className="underline">
              See it
            </a>
          )}
          {taken.reason !== "closed" && (
            <button onClick={() => pick(true)} disabled={busy} className="ml-2 underline">
              Take it anyway
            </button>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-warn">
          ⚠ {error}
        </p>
      )}

      <footer className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => pick()}
          disabled={busy}
          className="rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {busy ? "Checking…" : "I'll take this"}
        </button>
        <button onClick={() => setOpen(!open)} className="rounded-lg border border-border px-4 py-2 text-sm">
          {open ? "Less" : "Details"}
        </button>
        <details className="relative">
          <summary className="cursor-pointer list-none rounded-lg px-3 py-2 text-sm text-ink-2 hover:text-ink">
            Skip
          </summary>
          <div className="absolute z-10 mt-1 flex w-40 flex-col rounded-lg border border-border bg-surface p-1 shadow-lg">
            {SKIP_REASONS.map(([reason, label]) => (
              <button
                key={reason}
                onClick={() => skip(reason)}
                disabled={busy}
                className="rounded px-3 py-1.5 text-left text-sm hover:bg-page"
              >
                {label}
              </button>
            ))}
          </div>
        </details>
      </footer>
    </article>
  );
}
