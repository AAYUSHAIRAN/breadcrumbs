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
const MAX_LANGUAGES = 3;
const AUTO_TARGET = { beginner: "easy", intermediate: "medium", advanced: "hard" } as const;

export function defaultLanguages(user: Fingerprint) {
  const langs = user.skills.filter((s) => s.kind === "language");
  const strong = langs.filter((s) => s.level >= 0.15).map((s) => s.tech);
  return (strong.length ? strong : langs.map((s) => s.tech).slice(0, 1)).slice(0, MAX_LANGUAGES);
}

export function PreferencesForm({
  user,
  submitLabel,
  onSubmit,
}: {
  user: Fingerprint;
  submitLabel: string;
  onSubmit: (prefs: Preferences) => Promise<void>;
}) {
  const options = user.skills.filter((s) => s.kind === "language").map((s) => s.tech).slice(0, 8);
  const [languages, setLanguages] = useState(user.preferences.languages.length ? user.preferences.languages : defaultLanguages(user));
  const [difficulty, setDifficulty] = useState(user.preferences.difficulty);
  const [hours, setHours] = useState(user.preferences.hours_per_week);
  const [busy, setBusy] = useState(false);

  function toggle(lang: string) {
    setLanguages((ls) => (ls.includes(lang) ? ls.filter((l) => l !== lang) : ls.length < MAX_LANGUAGES ? [...ls, lang] : ls));
  }

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await onSubmit({ languages, difficulty, hours_per_week: hours });
        } finally {
          setBusy(false);
        }
      }}
      className="flex flex-col gap-6"
    >
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">
          Languages to search <span className="font-normal text-muted">(up to {MAX_LANGUAGES})</span>
        </legend>
        <div className="flex flex-wrap gap-2">
          {options.map((lang) => (
            <button
              key={lang}
              type="button"
              onClick={() => toggle(lang)}
              aria-pressed={languages.includes(lang)}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                languages.includes(lang) ? "border-accent bg-info-bg font-medium" : "border-border text-ink-2"
              }`}
            >
              {languages.includes(lang) ? "✓ " : ""}
              {lang}
            </button>
          ))}
          {!options.length && <p className="text-sm text-ink-2">We&apos;ll search across all languages.</p>}
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
