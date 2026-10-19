"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { preload, useSWRConfig } from "swr";

import { ApiError, api } from "@/lib/api";
import type { Fingerprint } from "@/lib/contracts";
import { setLogin, useLogin } from "@/lib/session";
import { PreferencesForm } from "../PreferencesForm";
import { SkillBars } from "../SkillBars";
import { CheckIcon } from "../ui/Icons";

// One-click profiles for people who don't want to use their own GitHub (or don't have one handy).
export const SAMPLES = [
  { login: "tiangolo", label: "creator of FastAPI · Python" },
  { login: "gaearon", label: "React core · JavaScript" },
  { login: "AAYUSHAIRAN", label: "one of us" },
];

const READING = ["Your public repositories", "Languages and dependency files", "Pull requests merged into other projects", "Your level"];
const MIN_READING_MS = 2400; // long enough to see the steps; real work usually takes about as long

type Step = { name: "enter" } | { name: "reading"; login: string } | { name: "reveal"; user: Fingerprint };

function Steps({ current }: { current: number }) {
  return (
    <ol className="flex gap-2 text-xs text-muted" aria-label="Onboarding progress">
      {["Who are you", "Reading GitHub", "Your profile"].map((label, i) => (
        <li key={label} className={`flex items-center gap-2 ${i <= current ? "text-ink" : ""}`}>
          <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] ${i < current ? "border-accent bg-accent text-white" : i === current ? "border-accent" : "border-border"}`}>
            {i < current ? "✓" : i + 1}
          </span>
          {label}
          {i < 2 && <span className="w-6 border-t border-border" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

function Reading({ login, onDone, onError }: { login: string; onDone: (u: Fingerprint) => void; onError: (m: string) => void }) {
  const [ticked, setTicked] = useState(0);
  // Callbacks change identity every parent render; keep the latest without re-running the fetch.
  const done = useRef({ onDone, onError });
  useEffect(() => {
    done.current = { onDone, onError };
  });
  useEffect(() => {
    const timer = setInterval(() => setTicked((t) => Math.min(t + 1, READING.length - 1)), MIN_READING_MS / READING.length);
    Promise.all([api.fingerprint(login), new Promise((r) => setTimeout(r, MIN_READING_MS))])
      .then(([user]) => done.current.onDone(user))
      .catch((e) =>
        done.current.onError(
          e instanceof ApiError && e.status === 404
            ? `There's no GitHub user called "${login}".`
            : e instanceof TypeError
              ? "Can't reach the Breadcrumbs API. Is the backend running (make api)?"
              : "Something went wrong reading GitHub.",
        ),
      )
      .finally(() => clearInterval(timer));
    return () => clearInterval(timer);
  }, [login]);

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <h1 className="text-3xl font-semibold tracking-tight">Reading @{login}&apos;s GitHub…</h1>
      <ul className="flex flex-col gap-3">
        {READING.map((label, i) => (
          <li key={label} className={`flex items-center gap-3 text-sm transition-opacity ${i <= ticked ? "opacity-100" : "opacity-30"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full ${i < ticked ? "bg-good-bg text-good" : "border border-border"}`}>
              {i < ticked ? <CheckIcon className="h-4 w-4" /> : <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />}
            </span>
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Onboarding() {
  const router = useRouter();
  const remembered = useLogin();
  const { mutate } = useSWRConfig();
  const sample = useSearchParams().get("u");
  // ?u=<login> (the landing page's sample links) skips straight to reading GitHub.
  const [step, setStep] = useState<Step>(sample ? { name: "reading", login: sample } : { name: "enter" });
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const index = { enter: 0, reading: 1, reveal: 2 }[step.name];

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-10 px-6 py-16">
      <Link href="/" className="font-mono text-sm text-muted hover:text-ink">
        breadcrumbs
      </Link>
      <Steps current={index} />

      {step.name === "enter" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const login = input.trim().replace(/^@/, "").replace(/^https?:\/\/github\.com\//, "").split("/")[0];
            if (login) {
              setError(null);
              setStep({ name: "reading", login });
            }
          }}
          className="flex flex-col gap-4"
        >
          <h1 className="text-3xl font-semibold tracking-tight">What&apos;s your GitHub username?</h1>
          <p className="text-ink-2">We read your public repos and merged PRs to work out what you know. Nothing is posted anywhere.</p>
          <div className="flex gap-2">
            <label htmlFor="login" className="sr-only">GitHub username</label>
            <input
              id="login"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. octocat"
              autoComplete="off"
              autoFocus
              className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 placeholder:text-muted focus:outline-2 focus:outline-accent"
            />
            <button type="submit" disabled={!input.trim()} className="rounded-lg bg-accent-strong px-5 py-3 font-medium text-white disabled:opacity-40">
              Continue
            </button>
          </div>
          {error && <p role="alert" className="text-sm text-warn">⚠ {error}</p>}
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
            <p className="text-sm text-ink-2">No GitHub handy? Try a sample profile:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((s) => (
                <button
                  key={s.login}
                  type="button"
                  onClick={() => {
                    setError(null);
                    setStep({ name: "reading", login: s.login });
                  }}
                  className="flex flex-col items-start rounded-lg border border-border px-3 py-2 text-left hover:border-accent hover:bg-info-bg"
                >
                  <span className="font-mono text-sm font-medium">@{s.login}</span>
                  <span className="text-xs text-ink-2">{s.label}</span>
                </button>
              ))}
            </div>
          </div>
          {remembered && (
            <p className="text-sm text-ink-2">
              Or{" "}
              <Link href="/home" className="font-medium text-accent-strong hover:underline">
                continue as @{remembered} →
              </Link>
            </p>
          )}
        </form>
      )}

      {step.name === "reading" && (
        <Reading
          login={step.login}
          onDone={(user) => {
            mutate(["fingerprint", user.login], user, { revalidate: false });
            setStep({ name: "reveal", user });
          }}
          onError={(message) => {
            setError(message);
            setStep({ name: "enter" });
          }}
        />
      )}

      {step.name === "reveal" && (
        <div className="flex flex-col gap-8">
          <div className="flex items-center gap-4">
            {step.user.avatar_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={step.user.avatar_url} alt="" className="h-14 w-14 rounded-full" />
            )}
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Hi {step.user.name?.split(" ")[0] ?? step.user.login}, here&apos;s what we found</h1>
              <p className="text-ink-2">
                <span className="capitalize">{step.user.level}</span> · {step.user.merged_prs} merged PRs in other projects ·{" "}
                {step.user.dependencies.length} libraries you depend on
              </p>
            </div>
          </div>
          <section className="rounded-xl border border-border bg-surface p-5">
            <h2 className="mb-2 text-sm font-medium">Your skills</h2>
            <SkillBars skills={step.user.skills} />
            <p className="mt-3 text-xs text-muted">
              From your public repos (recent ones count more) and PRs merged into other projects (count more still).
            </p>
          </section>
          <PreferencesForm
            user={step.user}
            submitLabel="Find my issues →"
            onSubmit={async (prefs) => {
              const user = await api.setPreferences(step.user.login, prefs);
              mutate(["fingerprint", user.login], user, { revalidate: false });
              preload(["matches", user.login], () => api.matches(user.login));
              setLogin(user.login);
              router.push("/discover");
            }}
          />
        </div>
      )}
    </main>
  );
}
