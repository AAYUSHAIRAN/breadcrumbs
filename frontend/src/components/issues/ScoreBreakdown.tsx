import type { IssueCard } from "@/lib/contracts";

// Mirrors backend/app/discovery/rank.py WEIGHTS.
const PARTS: { key: keyof IssueCard["breakdown"]; label: string; weight: number; hint: string }[] = [
  { key: "skill", label: "Skill match", weight: 0.35, hint: "How well you know the language or library" },
  { key: "difficulty", label: "Right difficulty", weight: 0.2, hint: "Closeness to the difficulty you chose" },
  { key: "maintainer", label: "Maintainer speed", weight: 0.2, hint: "How fast maintainers respond to PRs" },
  { key: "newcomers", label: "Newcomer friendly", weight: 0.15, hint: "Newcomer PRs merged in the last 90 days" },
  { key: "freshness", label: "Recently active", weight: 0.1, hint: "How recently the issue was updated" },
];

/** Why the fit is what it is: each component's score, with its weight. One hue, bars on a shared 0–100 scale. */
export function ScoreBreakdown({ card }: { card: IssueCard }) {
  return (
    <table className="w-full border-separate border-spacing-y-1.5 text-sm">
      <caption className="mb-1 text-left text-xs text-muted">
        Fit {Math.round(card.fit * 100)}% = weighted sum of these
        {card.in_dependencies && " (+5 for your dependency)"}
        {card.claimed && " (×0.3, someone claimed it)"}
      </caption>
      <tbody>
        {PARTS.map((p) => {
          const v = Math.round((card.breakdown[p.key] ?? 0) * 100);
          return (
            <tr key={p.key} title={p.hint}>
              <th scope="row" className="whitespace-nowrap pr-3 text-left font-normal text-ink-2">
                {p.label} <span className="font-mono text-xs text-muted">×{p.weight}</span>
              </th>
              <td className="w-full">
                <div className="h-2 w-full rounded-full bg-track">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(v, 2)}%` }} />
                </div>
              </td>
              <td className="w-10 pl-3 text-right font-mono text-xs">{v}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
