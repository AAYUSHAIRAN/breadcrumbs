"use client";

import Link from "next/link";

import { issuePath } from "@/lib/api";
import type { Attempt } from "@/lib/contracts";
import { ago } from "@/lib/format";
import { useAttempts } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { isActive, STATUS_LABEL } from "../attempts/progress";
import { Stepper } from "../attempts/Stepper";
import { useRemoveAttempt } from "../attempts/useRemoveAttempt";
import { EmptyState, PageHeader, Skeleton } from "../ui/States";

function Row({ a, onRemove }: { a: Attempt; onRemove: () => void }) {
  return (
    <li className="flex items-center gap-2">
      <Link
        href={`/trail/${issuePath(a.issue_id)}`}
        className="grid flex-1 items-center gap-4 rounded-xl border border-border bg-surface p-4 hover:border-accent/50 md:grid-cols-[1fr_16rem]"
      >
        <div className="min-w-0">
          <p className="truncate font-medium">{a.issue_title}</p>
          <p className="text-xs text-ink-2">
            <span className="font-mono">{a.issue_id}</span> ·{" "}
            {STATUS_LABEL[a.status]} · active {ago(a.last_activity_at)}
          </p>
        </div>
        <Stepper status={a.status} compact />
      </Link>
      <button
        onClick={onRemove}
        aria-label={`Remove ${a.issue_id} from your trail`}
        className="rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface hover:text-warn"
      >
        Remove
      </button>
    </li>
  );
}

export function TrailView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const { data } = useAttempts(login);
  const remove = useRemoveAttempt(login);
  const groups: [string, Attempt[]][] = data
    ? [
        ["In progress", data.filter(isActive)],
        ["Merged", data.filter((a) => a.status === "merged")],
        [
          "Closed",
          data.filter((a) => a.status === "closed" || a.status === "abandoned"),
        ],
      ]
    : [];

  return (
    <>
      <PageHeader
        title="My trail"
        subtitle="Every issue you've picked, from first comment to merged PR."
      />
      {!data ? (
        <Skeleton className="h-40" />
      ) : data.length === 0 ? (
        <EmptyState
          title="Your trail starts with one issue"
          body="Pick an issue in Discover. It'll show up here and we'll follow it over time."
          action={{ label: "Discover issues", href: "/discover" }}
        />
      ) : (
        groups
          .filter(([, items]) => items.length)
          .map(([title, items]) => (
            <section key={title} className="flex flex-col gap-2">
              <h2 className="text-sm font-medium">
                {title} <span className="text-muted">· {items.length}</span>
              </h2>
              <ul className="flex flex-col gap-2">
                {items.map((a) => (
                  <Row key={a.id} a={a} onRemove={() => remove(a)} />
                ))}
              </ul>
            </section>
          ))
      )}
    </>
  );
}
