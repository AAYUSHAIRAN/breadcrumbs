"use client";

import Link from "next/link";
import { useState } from "react";

import { issuePath, type Unavailable } from "@/lib/api";
import type { IssueCard } from "@/lib/contracts";
import { useWhy } from "@/lib/hooks";
import { GraphView } from "../graph/GraphView";
import { BookmarkIcon, ExternalIcon } from "../ui/Icons";
import { Meter } from "../Meter";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { useIssueActions } from "./useIssueActions";
import { WhyChips } from "./WhyChips";

const SKIP_REASONS = [
  ["not_interested", "Not interested"],
  ["too_hard", "Too hard"],
  ["too_easy", "Too easy"],
  ["wrong_tech", "Wrong tech"],
] as const;

/** Everything needed to decide on an issue. Used in the Discover side panel. */
export function IssueSummary({ login, card, standalone }: { login: string; card: IssueCard; standalone?: boolean }) {
  const actions = useIssueActions(login);
  const [busy, setBusy] = useState(false);
  const [taken, setTaken] = useState<Unavailable | null>(null);
  const why = useWhy(login, card.id, true);

  async function pick(force = false) {
    setBusy(true);
    try {
      setTaken(await actions.pick(card, force));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">
          <span className="font-mono">{card.repo}</span>
          <span aria-hidden>·</span>
          <span>★ {card.repo_stars.toLocaleString()}</span>
          <span aria-hidden>·</span>
          <span className="rounded border border-border px-1.5 py-0.5">{card.difficulty}</span>
        </div>
        <h2 className="text-xl font-semibold leading-snug">
          {card.title} <span className="font-mono text-base font-normal text-muted">#{card.number}</span>
        </h2>
      </header>

      <WhyChips why={card.why} />

      <div className="grid grid-cols-2 gap-4">
        <Meter label="Fit" value={card.fit} hint="Weighted: skill, difficulty, maintainer speed, newcomer merges, freshness" />
        <Meter label="Merge chance" value={card.merge_forecast} hint="Rough: newcomer merge rate here × difficulty × maintainer speed" />
      </div>

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

      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => pick()} disabled={busy} className="rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Checking it's still free…" : "I'll take this"}
        </button>
        <button onClick={() => actions.toggleSave(card)} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm">
          <BookmarkIcon className={`h-4 w-4 ${card.saved ? "fill-current" : ""}`} />
          {card.saved ? "Saved" : "Save"}
        </button>
        <details className="relative">
          <summary className="cursor-pointer list-none rounded-lg px-3 py-2 text-sm text-ink-2 hover:text-ink">Skip ▾</summary>
          <div className="absolute z-10 mt-1 flex w-40 flex-col rounded-lg border border-border bg-surface p-1 shadow-lg">
            {SKIP_REASONS.map(([reason, label]) => (
              <button key={reason} onClick={() => actions.skip(card, reason)} className="rounded px-3 py-1.5 text-left text-sm hover:bg-page">
                {label}
              </button>
            ))}
          </div>
        </details>
        <a href={card.url} target="_blank" rel="noreferrer" className="ml-auto flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
          GitHub <ExternalIcon className="h-4 w-4" />
        </a>
      </div>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">Why it fits you</h3>
        <ScoreBreakdown card={card} />
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">The path in your graph</h3>
        {why.data ? (
          <GraphView view={why.data} direction="vertical" title={`Graph path from you to ${card.repo}#${card.number}`} />
        ) : (
          <div className="h-32 animate-pulse rounded-xl border border-border bg-surface" />
        )}
      </section>

      {!standalone && (
        <Link href={`/issues/${issuePath(card.id)}`} className="text-sm text-accent-strong hover:underline">
          Open full issue page →
        </Link>
      )}
    </div>
  );
}
