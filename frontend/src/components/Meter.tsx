/** A single ratio against a limit: same-hue track and fill, value in text ink. */
export function Meter({ label, value, hint }: { label: string; value: number; hint: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex flex-col gap-1" title={hint}>
      <div className="flex justify-between text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="font-mono text-ink">{pct}%</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-1.5 w-full overflow-hidden rounded-full bg-track"
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
