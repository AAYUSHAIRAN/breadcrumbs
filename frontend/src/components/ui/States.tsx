import Link from "next/link";

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl border border-border bg-surface ${className}`} />;
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { label: string; href: string };
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-border p-8">
      <p className="font-medium">{title}</p>
      <p className="text-sm text-ink-2">{body}</p>
      {action && (
        <Link href={action.href} className="mt-2 rounded-lg bg-accent-strong px-4 py-2 text-sm font-medium text-white">
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-lg bg-warn-bg p-4 text-sm text-warn">
      ⚠ {message}
    </p>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}
