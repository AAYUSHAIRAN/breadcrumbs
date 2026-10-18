"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useFingerprint } from "@/lib/hooks";
import { setLogin, useLogin } from "@/lib/session";
import { CompassIcon, HomeIcon, MenuIcon, TrailIcon, UserIcon } from "../ui/Icons";
import { ToastProvider } from "../ui/Toast";

const NAV = [
  { href: "/home", label: "Home", Icon: HomeIcon },
  { href: "/discover", label: "Discover", Icon: CompassIcon },
  { href: "/trail", label: "My trail", Icon: TrailIcon },
  { href: "/profile", label: "Profile", Icon: UserIcon },
];

function Sidebar({ login, onNavigate }: { login: string | undefined; onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: user } = useFingerprint(login);

  return (
    <nav className="flex h-full flex-col gap-6 p-4">
      <Link href="/home" onClick={onNavigate} className="px-2 font-mono text-sm font-medium">
        breadcrumbs
      </Link>
      <ul className="flex flex-col gap-1">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`) || (href === "/trail" && pathname.startsWith("/trail"));
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                  active ? "bg-info-bg font-medium text-ink" : "text-ink-2 hover:bg-surface hover:text-ink"
                }`}
              >
                <Icon />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="mt-auto flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
        {user?.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full" />
        ) : (
          <div className="h-8 w-8 rounded-full bg-hairline" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{user?.name ?? login ?? " "}</p>
          <button
            onClick={() => {
              setLogin(null);
              router.push("/start");
            }}
            className="text-xs text-ink-2 hover:text-ink"
          >
            Switch user
          </button>
        </div>
      </div>
    </nav>
  );
}

export function AppFrame({ children }: { children: React.ReactNode }) {
  const login = useLogin();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (login === null) router.replace("/start");
  }, [login, router]);

  // On the server we don't know the user yet (undefined): still render the frame and the
  // page, which shows its loading state, so the pre-rendered shell isn't empty.
  if (login === null) return null; // redirecting to /start

  return (
    <ToastProvider>
      <div className="flex min-h-screen w-full">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r border-border lg:block">
          <Sidebar login={login} />
        </aside>

        {menuOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal>
            <button aria-label="Close menu" className="absolute inset-0 bg-black/40" onClick={() => setMenuOpen(false)} />
            <aside className="absolute inset-y-0 left-0 w-64 bg-page">
              <Sidebar login={login} onNavigate={() => setMenuOpen(false)} />
            </aside>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-3 border-b border-border px-4 py-3 lg:hidden">
            <button aria-label="Open menu" onClick={() => setMenuOpen(true)}>
              <MenuIcon />
            </button>
            <span className="font-mono text-sm font-medium">breadcrumbs</span>
          </header>
          <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-8">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
