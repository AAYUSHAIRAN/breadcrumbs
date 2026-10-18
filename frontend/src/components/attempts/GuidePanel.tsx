"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";

import { ApiError, api } from "@/lib/api";
import type { Guide } from "@/lib/contracts";
import { useToast } from "../ui/Toast";

// Shown while the agent runs (~20–40s). These are its real steps, in order.
const RUNNING = [
  "Reading your profile from the graph…",
  "Recalling what it remembers about you…",
  "Recalling what Breadcrumbs learned about this repo…",
  "Reading the repo's CONTRIBUTING, PR template and CI on GitHub…",
  "Writing your drafts with Claude…",
  "Saving what it learned to the graph…",
];

function Copy({ text, label = "Copy" }: { text: string; label?: string }) {
  const toast = useToast();
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        toast({ message: "Copied" });
      }}
      className="rounded border border-border px-2 py-0.5 text-xs hover:bg-page"
    >
      {label}
    </button>
  );
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function GuidePanel({ login, issueId, fallback }: { login: string; issueId: string; fallback: React.ReactNode }) {
  const key = login ? ["guide", issueId, login] : null;
  const { data, mutate } = useSWR(key, () => api.guide(login, issueId), { revalidateOnFocus: false });
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, RUNNING.length - 1)), 4000);
    return () => clearInterval(t);
  }, [running]);

  async function run() {
    setStep(0);
    setRunning(true);
    setError(null);
    try {
      await mutate(await api.writeGuide(login, issueId), { revalidate: false });
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : "The Guide couldn't run. Is the backend up?");
    } finally {
      setRunning(false);
    }
  }

  const guide = data && "claim_comment" in data ? (data as Guide) : null;

  if (running) {
    return (
      <div className="flex flex-col gap-3 rounded-xl border border-accent bg-info-bg p-6" aria-live="polite">
        <p className="font-medium">✨ Guide is working</p>
        <ol className="flex flex-col gap-2 text-sm">
          {RUNNING.map((s, i) => (
            <li key={s} className={i <= step ? "text-ink" : "text-muted"}>
              {i < step ? "✓" : i === step ? "◌" : "·"} {s}
            </li>
          ))}
        </ol>
      </div>
    );
  }

  if (!guide) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 rounded-xl border border-accent bg-info-bg p-6">
          <p className="text-lg font-medium">✨ Let Guide write these for you</p>
          <p className="max-w-2xl text-sm text-ink-2">
            Guide reads this repo&apos;s own CONTRIBUTING, PR template and CI, plus what your graph knows about you, and writes a
            claim comment, the exact setup commands and a PR description that follow the repo&apos;s rules. It remembers what it
            learns for next time.
          </p>
          <button onClick={run} className="self-start rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white">
            ✨ Write with Guide
          </button>
          {error && <p role="alert" className="text-sm text-warn">⚠ {error}</p>}
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted">Generic templates, until Guide runs:</p>
          {fallback}
        </div>
      </div>
    );
  }

  const setup = guide.setup_steps.map((s) => s.command).join("\n");
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4 text-sm">
        <span>
          ✨ Written by Guide from <span className="font-mono text-xs">{guide.sources.join(", ") || "no rule files"}</span>, your
          profile, {guide.used_memories} notes about you and {guide.used_repo_facts} facts already known about this repo.
        </span>
        <button onClick={run} className="rounded-lg border border-border px-3 py-1.5 text-sm">
          Rewrite
        </button>
      </div>

      <details className="rounded-xl border border-border bg-surface p-4 text-sm">
        <summary className="cursor-pointer font-medium">Agent trace · {guide.trace.length} steps</summary>
        <ol className="mt-3 flex flex-col gap-3">
          {guide.trace.map((t, i) => (
            <li key={t.step}>
              <p>
                <span className="font-mono text-xs text-muted">{i + 1}.</span> {t.step} <span className="text-ink-2">· {t.detail}</span>
              </p>
              {t.query && <pre className="mt-1 overflow-x-auto rounded bg-page p-2 font-mono text-[11px]">{t.query}</pre>}
            </li>
          ))}
        </ol>
      </details>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="1. Claim it" action={<Copy text={guide.claim_comment} />}>
          <pre className="whitespace-pre-wrap rounded-lg bg-page p-3 font-sans text-sm">{guide.claim_comment}</pre>
        </Card>
        <Card title="2. Set up" action={<Copy text={setup} label="Copy all" />}>
          <ol className="flex flex-col gap-2">
            {guide.setup_steps.map((s) => (
              <li key={s.command} className="flex flex-col gap-0.5">
                <code className="rounded bg-page px-2 py-1 font-mono text-[12px]">{s.command}</code>
                <span className="text-xs text-ink-2">{s.why}</span>
              </li>
            ))}
          </ol>
        </Card>
        <Card title="3. Open the PR" action={<Copy text={`${guide.pr_title}\n\n${guide.pr_description}`} />}>
          <p className="font-mono text-xs">{guide.pr_title}</p>
          <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg bg-page p-3 font-sans text-sm">{guide.pr_description}</pre>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Tips for you">
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
            {guide.tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </Card>
        <Card title="Learned about this repo">
          <ul className="flex flex-col gap-2 text-sm">
            {guide.learned_about_repo.map((f) => (
              <li key={f.fact}>
                {f.fact} <span className="font-mono text-xs text-muted">· {f.source}</span>
              </li>
            ))}
            {!guide.learned_about_repo.length && <li className="text-ink-2">Nothing new.</li>}
          </ul>
          <p className="text-xs text-muted">Saved to the repo in the graph, so the next newcomer starts with it.</p>
        </Card>
        <Card title="Remembered about you">
          <ul className="flex flex-col gap-2 text-sm">
            {guide.learned_about_user.map((f) => (
              <li key={f.fact}>{f.fact}</li>
            ))}
            {!guide.learned_about_user.length && <li className="text-ink-2">Nothing new this time.</li>}
          </ul>
          <p className="text-xs text-muted">See or delete these on your Profile.</p>
        </Card>
      </div>
    </div>
  );
}
