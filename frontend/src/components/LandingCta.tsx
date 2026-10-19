"use client";

import Link from "next/link";

import { useLogin } from "@/lib/session";
import { SAMPLES } from "./screens/Onboarding";

export function LandingCta() {
  const login = useLogin();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          href="/start"
          className="rounded-lg bg-accent-strong px-5 py-3 font-medium text-white"
        >
          Find issues you can land →
        </Link>
        {login && (
          <Link href="/home" className="text-sm text-ink-2 hover:text-ink">
            Continue as @{login}
          </Link>
        )}
      </div>
      <p className="text-sm text-ink-2">
        Or try a sample profile:{" "}
        {SAMPLES.map((s, i) => (
          <span key={s.login}>
            {i > 0 && " · "}
            <Link
              href={`/start?u=${s.login}`}
              className="font-mono text-accent-strong hover:underline"
            >
              @{s.login}
            </Link>
          </span>
        ))}
      </p>
    </div>
  );
}
