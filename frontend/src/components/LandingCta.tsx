"use client";

import Link from "next/link";

import { useLogin } from "@/lib/session";

export function LandingCta() {
  const login = useLogin();
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Link href="/start" className="rounded-lg bg-accent-strong px-5 py-3 font-medium text-white">
        Find issues you can land →
      </Link>
      {login && (
        <Link href="/home" className="text-sm text-ink-2 hover:text-ink">
          Continue as @{login}
        </Link>
      )}
    </div>
  );
}
