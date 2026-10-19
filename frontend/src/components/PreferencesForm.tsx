"use client";

import { useState } from "react";

import type { Fingerprint, Preferences } from "@/lib/contracts";

const DIFFICULTIES: { value: Preferences["difficulty"]; label: string; body: string }[] = [
  { value: "auto", label: "Pick for me", body: "One step above your level" },
  { value: "easy", label: "Easy", body: "Good first issues, small scope" },
  { value: "medium", label: "Medium", body: "Some context needed" },
  { value: "hard", label: "Hard", body: "Core code, bigger changes" },
];
const HOURS = [2, 5, 10, 20];
const MAX_TECH = 5; // mirrors MAX_LANGUAGES in backend/app/discovery/search.py
const MAX_FROM_PROFILE = 10;
const AUTO_TARGET = { beginner: "easy", intermediate: "medium", advanced: "hard" } as const;
// One-tap suggestions. Languages are searched by repo language, the rest by GitHub topic.
const SUGGESTIONS = ["react", "next.js", "typescript", "python", "rust", "go", "vue", "fastapi", "django", "svelte", "docker"];

export function defaultLanguages(user: Fingerprint) {
  const langs = user.skills.filter((s) => s.kind === "language");
  const strong = langs.filter((s) => s.level >= 0.15).map((s) => s.tech);
  return (strong.length ? strong : langs.map((s) => s.tech).slice(0, 1)).slice(0, 3);
}

const clean = (t: string) => t.trim().toLowerCase();

export function PreferencesForm({
  user,
  submitLabel,
  onSubmit,
}: {
  user: Fingerprint;
  submitLabel: string;
  onSubmit: (prefs: Preferences) => Promise<void>;
}) {
  // From the profile: languages and frameworks, strongest first.
  const fromProfile = user.skills.filter((s) => s.kind === "language" || s.kind === "framework").slice(0, MAX_FROM_PROFILE);
  const known = new Set(fromProfile.map((s) => s.tech));
  const [chosen, setChosen] = useState(user.preferences.languages.length ? user.preferences.languages : defaultLanguages(user));
  const [custom, setCustom] = useState("");
  const [difficulty, setDifficulty] = useState(user.preferences.difficulty);
  const [hours, setHours] = useState(user.preferences.hours_per_week);
  const [busy, setBusy] = useState(false);
  const full = chosen.length >= MAX_TECH;

  function toggle(tech: string) {
    const t = clean(tech);
    setChosen((cs) => (cs.includes(t) ? cs.filter((c) => c !== t) : cs.length < MAX_TECH ? [...cs, t] : cs));
  }
  function addCustom() {
    const t = clean(custom);
    if (t && !chosen.includes(t) && !full) setChosen((cs) => [...cs, t]);
    setCustom("");
  }

  const extra = chosen.filter((c) => !known.has(c)); // custom or suggested picks, shown as removable chips
  const chip = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-sm disabled:opacity-40 ${on ? "border-accent bg-info-bg font-medium" : "border-border text-ink-2 hover:text-ink"}`;

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await onSubmit({ languages: chosen, difficulty, hours_per_week: hours });
        } finally {
          setBusy(false);
        }
      }}
      className="flex flex-col gap-6"
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-medium">
          What to search for{" "}
          <span className="font-normal text-muted">
            ({chosen.length}/{MAX_TECH} picked · we search up to {MAX_TECH} at a time)
          </span>
        </legend>

        <div className="flex flex-col gap-1.5">
          <p className="text-xs text-muted">
            From your profile: your languages and frameworks{fromProfile.length === MAX_FROM_PROFILE ? ` (top ${MAX_FROM_PROFILE})` : ""}
          </p>
          <div className="flex flex-wrap gap-2">
            {fromProfile.map((s) => {
              const on = chosen.includes(s.tech);
              return (
                <button key={s.tech} type="button" onClick={() => toggle(s.tech)} aria-pressed={on} disabled={!on && full} className={chip(on)}>
                  {on ? "✓ " : ""}
                  {s.tech}
                  {s.kind === "framework" && <span className="ml-1.5 rounded bg-page px-1 py-0.5 text-[10px] uppercase tracking-wide text-muted">framework</span>}
                </button>
              );
            })}
            {!fromProfile.length && <p className="text-sm text-ink-2">No public code yet: add what you want to work with below.</p>}
          </div>
        </div>

        {extra.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs text-muted">Added by you</p>
            <div className="flex flex-wrap gap-2">
              {extra.map((t) => (
                <span key={t} className="flex items-center gap-1 rounded-full border border-accent bg-info-bg py-1.5 pl-3 pr-1.5 text-sm font-medium">
                  {t}
                  <button type="button" onClick={() => toggle(t)} aria-label={`Remove ${t}`} className="rounded-full px-1.5 text-ink-2 hover:bg-page hover:text-ink">
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex gap-2">
            <label htmlFor="custom-tech" className="sr-only">
              Add a language, framework or tool
            </label>
            <input
              id="custom-tech"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustom();
                }
              }}
              disabled={full}
              placeholder={full ? `${MAX_TECH} picked: remove one to add another` : "+ Add any language, framework or tool"}
              className="w-72 rounded-lg border border-border bg-surface px-3 py-2 text-sm placeholder:text-muted disabled:opacity-50"
            />
            <button type="button" onClick={addCustom} disabled={!custom.trim() || full} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.filter((t) => !chosen.includes(t) && !known.has(t)).map((t) => (
              <button key={t} type="button" onClick={() => toggle(t)} disabled={full} className="rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-40">
                + {t}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">Things you add count as a medium skill, even without public code in them.</p>
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">Difficulty</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {DIFFICULTIES.map((d) => (
            <label
              key={d.value}
              className={`cursor-pointer rounded-lg border p-3 text-sm ${difficulty === d.value ? "border-accent bg-info-bg" : "border-border"}`}
            >
              <input type="radio" name="difficulty" value={d.value} checked={difficulty === d.value} onChange={() => setDifficulty(d.value)} className="sr-only" />
              <span className="block font-medium">{d.label}</span>
              <span className="block text-xs text-ink-2">{d.value === "auto" ? `${d.body}: ${AUTO_TARGET[user.level]}` : d.body}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">Time you have per week</legend>
        <div className="flex flex-wrap gap-2">
          {HOURS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHours(h)}
              aria-pressed={hours === h}
              className={`rounded-full border px-3 py-1.5 text-sm ${hours === h ? "border-accent bg-info-bg font-medium" : "border-border text-ink-2"}`}
            >
              {h === 20 ? "10+ hours" : `~${h} hours`}
            </button>
          ))}
        </div>
      </fieldset>

      <button type="submit" disabled={busy} className="self-start rounded-lg bg-accent-strong px-5 py-3 font-medium text-white disabled:opacity-40">
        {busy ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
