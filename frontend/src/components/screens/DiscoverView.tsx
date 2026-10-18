"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { issuePath, parseIssueRef } from "@/lib/api";
import type { Difficulty, IssueCard } from "@/lib/contracts";
import { useMatches, useSaved } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { IssueRow } from "../issues/IssueRow";
import { IssueSummary } from "../issues/IssueSummary";
import { useIssueActions } from "../issues/useIssueActions";
import { EmptyState, ErrorNote, PageHeader, Skeleton } from "../ui/States";

// Shown while the first (uncached) match takes a few seconds. These are the real steps.
const WORKING = [
  "Finding active projects in your languages…",
  "Looking at the libraries you depend on…",
  "Checking who has already claimed what…",
  "Measuring how fast maintainers reply…",
];

type Sort = "fit" | "merge" | "recent";
const SORTS: Record<Sort, [string, (a: IssueCard, b: IssueCard) => number]> = {
  fit: ["Best fit", (a, b) => b.fit - a.fit],
  merge: ["Merge chance", (a, b) => b.merge_forecast - a.merge_forecast],
  recent: ["Recently active", (a, b) => b.updated_at.localeCompare(a.updated_at)],
};

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={`rounded-full border px-3 py-1 text-sm ${on ? "border-accent bg-info-bg text-ink" : "border-border text-ink-2 hover:text-ink"}`}
    >
      {children}
    </button>
  );
}

function PasteIssue() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const ref = parseIssueRef(value);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ref) router.push(`/issues/${issuePath(ref)}`);
      }}
      className="flex gap-2"
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Paste a GitHub issue URL"
        aria-label="Check any GitHub issue"
        className="w-64 rounded-lg border border-border bg-surface px-3 py-2 text-sm placeholder:text-muted"
      />
      <button disabled={!ref} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">
        Check fit
      </button>
    </form>
  );
}

export function DiscoverView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const router = useRouter();
  const matches = useMatches(login);
  const saved = useSaved(login);
  const actions = useIssueActions(login);

  const [tab, setTab] = useState<"for-you" | "saved">("for-you");
  const [tech, setTech] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);
  const [depsOnly, setDepsOnly] = useState(false);
  const [hideWarnings, setHideWarnings] = useState(false);
  const [sort, setSort] = useState<Sort>("fit");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  const source = tab === "saved" ? saved.data : matches.data?.issues;
  const techs = useMemo(() => [...new Set((matches.data?.issues ?? []).map((c) => c.tech).filter(Boolean))], [matches.data]);
  const shown = useMemo(
    () =>
      (source ?? [])
        .filter((c) => !tech || c.tech === tech)
        .filter((c) => !difficulty || c.difficulty === difficulty)
        .filter((c) => !depsOnly || c.in_dependencies)
        .filter((c) => !hideWarnings || !c.why.some((w) => w.kind === "warning"))
        .sort(SORTS[sort][1]),
    [source, tech, difficulty, depsOnly, hideWarnings, sort],
  );
  const selected = shown.find((c) => c.id === selectedId) ?? shown[0] ?? null;
  const filtered = tech || difficulty || depsOnly || hideWarnings;

  useEffect(() => {
    if (matches.data) return;
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, WORKING.length - 1)), 2500);
    return () => clearInterval(timer);
  }, [matches.data]);

  // Keyboard: j/k to move, enter to open, s to save, x to skip.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey || !selected) return;
      const i = shown.findIndex((c) => c.id === selected.id);
      if (e.key === "j") setSelectedId(shown[Math.min(i + 1, shown.length - 1)]?.id ?? null);
      else if (e.key === "k") setSelectedId(shown[Math.max(i - 1, 0)]?.id ?? null);
      else if (e.key === "Enter") router.push(`/issues/${issuePath(selected.id)}`);
      else if (e.key === "s") actions.toggleSave(selected);
      else if (e.key === "x") actions.skip(selected, "not_interested");
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shown, selected, router, actions]);

  return (
    <>
      <PageHeader title="Discover" subtitle="Unclaimed, recently active issues in repos where maintainers reply and newcomers get merged.">
        <PasteIssue />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-4">
        {(["for-you", "saved"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`mr-2 border-b-2 pb-1 text-sm ${tab === t ? "border-accent font-medium" : "border-transparent text-ink-2"}`}
          >
            {t === "for-you" ? `For you${matches.data ? ` · ${matches.data.issues.length}` : ""}` : `Saved${saved.data ? ` · ${saved.data.length}` : ""}`}
          </button>
        ))}
        <span className="mx-2 h-5 w-px bg-hairline" aria-hidden />
        {techs.map((t) => (
          <Toggle key={t} on={tech === t} onClick={() => setTech(tech === t ? null : t)}>
            {t}
          </Toggle>
        ))}
        {(["easy", "medium", "hard"] as const).map((d) => (
          <Toggle key={d} on={difficulty === d} onClick={() => setDifficulty(difficulty === d ? null : d)}>
            {d}
          </Toggle>
        ))}
        <Toggle on={depsOnly} onClick={() => setDepsOnly(!depsOnly)}>
          📦 my dependencies
        </Toggle>
        <Toggle on={hideWarnings} onClick={() => setHideWarnings(!hideWarnings)}>
          no warnings
        </Toggle>
        <label className="ml-auto flex items-center gap-2 text-sm text-ink-2">
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="rounded-lg border border-border bg-surface px-2 py-1 text-ink">
            {Object.entries(SORTS).map(([k, [label]]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {matches.data?.stale && <ErrorNote message="GitHub isn't responding, so some of this may be out of date." />}
      {matches.error && <ErrorNote message="Couldn't load matches. Is the backend running (make api)?" />}

      {!source && !matches.error ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]" aria-live="polite">
          <div className="flex flex-col gap-3">
            <p className="text-sm text-ink-2">{WORKING[step]}</p>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
          <Skeleton className="hidden h-[32rem] lg:block" />
        </div>
      ) : shown.length === 0 ? (
        tab === "saved" && !filtered ? (
          <EmptyState title="Nothing saved yet" body="Save issues you might want later. Press s on any issue in the list." />
        ) : filtered ? (
          <EmptyState title="No issues match these filters" body="Try removing a filter." />
        ) : (
          <EmptyState title="No good matches right now" body="New issues show up every day. You can also paste any GitHub issue URL above to check its fit." />
        )
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <ul className="flex flex-col gap-2">
            {shown.map((card) => (
              <li key={card.id}>
                <IssueRow
                  card={card}
                  selected={card.id === selected?.id}
                  onSelect={() => {
                    if (window.matchMedia("(min-width: 1024px)").matches) setSelectedId(card.id);
                    else router.push(`/issues/${issuePath(card.id)}`);
                  }}
                />
              </li>
            ))}
            <li className="pt-2 text-xs text-muted">
              Keys: <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>enter</kbd> open · <kbd>s</kbd> save · <kbd>x</kbd> skip
            </li>
          </ul>
          {selected && (
            <aside className="hidden self-start rounded-xl border border-border bg-surface p-6 lg:sticky lg:top-6 lg:block">
              <IssueSummary key={selected.id} login={login} card={selected} />
            </aside>
          )}
        </div>
      )}
    </>
  );
}
