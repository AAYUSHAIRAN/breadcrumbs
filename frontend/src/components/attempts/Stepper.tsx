import type { AttemptStatus } from "@/lib/contracts";
import { STEPS, stepOf } from "./progress";

export function Stepper({ status, compact }: { status: AttemptStatus; compact?: boolean }) {
  const current = stepOf(status);
  const changes = status === "changes_requested";
  return (
    <ol className="flex w-full items-center" aria-label={`Progress: ${STEPS[Math.max(current, 0)]}`}>
      {STEPS.map((label, i) => {
        const done = current > i || (current === i && status === "merged");
        const here = current === i && status !== "merged";
        return (
          <li key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <span
                className={`flex items-center justify-center rounded-full border-2 ${compact ? "h-3 w-3" : "h-7 w-7 text-xs"} ${
                  done ? "border-accent bg-accent text-white" : here ? "border-accent bg-surface text-accent" : "border-hairline bg-surface text-muted"
                }`}
                aria-current={here ? "step" : undefined}
              >
                {!compact && (done ? "✓" : i + 1)}
              </span>
              {!compact && (
                <span className={`whitespace-nowrap text-xs ${here || done ? "text-ink" : "text-muted"}`}>
                  {here && changes ? "Changes requested" : label}
                </span>
              )}
            </div>
            {i < STEPS.length - 1 && <span className={`mx-1 h-0.5 flex-1 ${current > i ? "bg-accent" : "bg-hairline"} ${compact ? "" : "mb-5"}`} />}
          </li>
        );
      })}
    </ol>
  );
}
