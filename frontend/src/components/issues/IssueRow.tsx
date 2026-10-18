import type { IssueCard } from "@/lib/contracts";

/** Compact list item for Discover and Home. */
export function IssueRow({ card, selected, onSelect }: { card: IssueCard; selected?: boolean; onSelect: () => void }) {
  const warn = card.why.some((w) => w.kind === "warning");
  return (
    <button
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={`flex w-full flex-col gap-1.5 rounded-xl border p-4 text-left transition-colors ${
        selected ? "border-accent bg-info-bg" : "border-border bg-surface hover:border-accent/50"
      }`}
    >
      <div className="flex items-center gap-2 text-xs text-ink-2">
        <span className="truncate font-mono">{card.repo}</span>
        <span className="rounded border border-border px-1.5">{card.difficulty}</span>
        {card.in_dependencies && <span title="One of your dependencies">📦</span>}
        {card.saved && <span title="Saved">🔖</span>}
        {warn && <span title={card.why.find((w) => w.kind === "warning")?.label} className="text-warn">⚠</span>}
        <span className="ml-auto font-mono text-ink">{Math.round(card.fit * 100)}%</span>
      </div>
      <p className="line-clamp-2 text-sm font-medium leading-snug">{card.title}</p>
    </button>
  );
}
