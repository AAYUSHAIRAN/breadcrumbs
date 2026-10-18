"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";

import { api } from "@/lib/api";
import { useFingerprint, useTrailGraph } from "@/lib/hooks";
import { useLogin } from "@/lib/session";
import { GraphView } from "../graph/GraphView";
import { MemoryList } from "../MemoryList";
import { PreferencesForm } from "../PreferencesForm";
import { SkillBars } from "../SkillBars";
import { PageHeader, Skeleton } from "../ui/States";
import { useToast } from "../ui/Toast";

// Trail graph reads left to right: your skills ← you → your issues → their repos.
const TRAIL_LEVELS = { tech: 0, user: 1, issue: 2, repo: 3, fact: 4 } as const;

export function ProfileView() {
  const login = useLogin() ?? ""; // "" until known: hooks wait, nothing fetches
  const { data: user } = useFingerprint(login);
  const graph = useTrailGraph(login);
  const { mutate } = useSWRConfig();
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);

  return (
    <>
      <PageHeader title="Profile" subtitle="What we know about you, and how it changes as you contribute.">
        <button
          onClick={async () => {
            setRefreshing(true);
            try {
              await mutate(["fingerprint", login], api.fingerprint(login));
              await mutate(["trail-graph", login]);
              toast({ message: "Re-read your GitHub" });
            } finally {
              setRefreshing(false);
            }
          }}
          className="rounded-lg border border-border px-3 py-2 text-sm"
        >
          {refreshing ? "Reading GitHub…" : "Refresh from GitHub"}
        </button>
      </PageHeader>

      {user ? (
        <div className="flex items-center gap-4">
          {user.avatar_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.avatar_url} alt="" className="h-16 w-16 rounded-full" />
          )}
          <div>
            <p className="text-lg font-medium">{user.name ?? user.login}</p>
            <p className="text-sm text-ink-2">
              <a href={`https://github.com/${user.login}`} target="_blank" rel="noreferrer" className="font-mono hover:underline">
                @{user.login}
              </a>{" "}
              · <span className="capitalize">{user.level}</span> · {user.merged_prs} merged PRs in other projects
            </p>
          </div>
        </div>
      ) : (
        <Skeleton className="h-16" />
      )}

      <section className="flex flex-col gap-2">
        <h2 className="font-medium">Your trail, as a graph</h2>
        <p className="text-sm text-ink-2">Your strongest skills, the issues you&apos;ve picked, their repos, and what you&apos;ve learned. It grows with every attempt.</p>
        {graph.data ? <GraphView view={graph.data} levels={TRAIL_LEVELS} title="Your trail graph" /> : <Skeleton className="h-56" />}
      </section>

      <MemoryList login={login} />

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="mb-3 font-medium">Skills</h2>
          {user ? <SkillBars skills={user.skills} /> : <Skeleton className="h-40" />}
        </section>
        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="mb-3 font-medium">Preferences</h2>
          {user && (
            <PreferencesForm
              user={user}
              submitLabel="Save preferences"
              onSubmit={async (prefs) => {
                const updated = await api.setPreferences(login, prefs);
                await mutate(["fingerprint", login], updated, { revalidate: false });
                mutate(["matches", login]);
                toast({ message: "Saved. Updating your matches…" });
              }}
            />
          )}
        </section>
      </div>
    </>
  );
}
