import type { WhyChip } from "@/lib/contracts";

const STYLE: Record<WhyChip["kind"], { cls: string; icon: string }> = {
  skill: { cls: "bg-info-bg text-ink", icon: "" },
  dependency: { cls: "bg-info-bg text-ink", icon: "" },
  unclaimed: { cls: "bg-good-bg text-good", icon: "✓ " },
  fast_maintainer: { cls: "bg-good-bg text-good", icon: "✓ " },
  newcomers: { cls: "bg-good-bg text-good", icon: "✓ " },
  small_scope: { cls: "bg-good-bg text-good", icon: "✓ " },
  warning: { cls: "bg-warn-bg text-warn", icon: "⚠ " },
};

export function WhyChips({ why, limit }: { why: WhyChip[]; limit?: number }) {
  const shown = limit ? why.slice(0, limit) : why;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Why this issue">
      {shown.map((w) => (
        <li key={w.label} className={`rounded-full px-2.5 py-1 text-xs ${STYLE[w.kind].cls}`}>
          {STYLE[w.kind].icon}
          {w.label}
        </li>
      ))}
      {limit && why.length > limit && <li className="px-1 py-1 text-xs text-muted">+{why.length - limit}</li>}
    </ul>
  );
}
