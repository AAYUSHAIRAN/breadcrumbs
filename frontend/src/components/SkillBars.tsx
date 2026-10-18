import type { Skill } from "@/lib/contracts";

const SHOWN = 8;

/** One series, sorted by level: a bar per skill with its value direct-labelled. */
export function SkillBars({ skills }: { skills: Skill[] }) {
  const top = skills.slice(0, SHOWN);
  if (!top.length) {
    return <p className="text-sm text-ink-2">No public code to read skills from yet.</p>;
  }
  return (
    <table className="w-full border-separate border-spacing-y-1.5 text-sm">
      <caption className="sr-only">Skill levels, 0 to 100</caption>
      <tbody>
        {top.map((s) => {
          const pct = Math.round(s.level * 100);
          return (
            <tr key={s.tech} className="group" title={`${s.tech}: ${pct}/100 · ${s.kind} · ${s.source}`}>
              <th scope="row" className="w-28 truncate pr-3 text-left font-normal text-ink">
                {s.tech}
              </th>
              <td className="w-full">
                <div className="h-3 w-full rounded-r bg-transparent">
                  <div
                    className="h-full rounded-r bg-accent transition-opacity group-hover:opacity-80"
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
              </td>
              <td className="w-10 pl-3 text-right font-mono text-xs text-ink-2">{pct}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
