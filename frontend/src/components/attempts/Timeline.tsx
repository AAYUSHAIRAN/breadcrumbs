import type { Event } from "@/lib/contracts";
import { ago } from "@/lib/format";
import { EVENT_LABEL } from "./progress";

export function Timeline({ events }: { events: Event[] }) {
  const ordered = [...events].reverse();
  return (
    <ol className="relative flex flex-col gap-5 border-l border-hairline pl-6">
      {ordered.map((e) => (
        <li key={`${e.type}-${e.gh_id ?? e.at}`} className="relative">
          <span className="absolute -left-[1.85rem] top-1 h-3 w-3 rounded-full border-2 border-accent bg-surface" />
          <p className="text-sm font-medium">
            {e.url ? (
              <a href={e.url} target="_blank" rel="noreferrer" className="hover:underline">
                {EVENT_LABEL[e.type]}
              </a>
            ) : (
              EVENT_LABEL[e.type]
            )}
          </p>
          <p className="text-xs text-ink-2">
            <time dateTime={e.at} title={new Date(e.at).toLocaleString()}>
              {ago(e.at)}
            </time>
            {e.summary && e.summary !== EVENT_LABEL[e.type] && ` · ${e.summary}`}
          </p>
        </li>
      ))}
    </ol>
  );
}
