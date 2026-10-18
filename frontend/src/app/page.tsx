import { UsernameForm } from "@/components/UsernameForm";

const STEPS = [
  ["Your skills", "Read from your public repos, dependency files and merged PRs."],
  ["Issues you can land", "Unclaimed issues in active repos where maintainers reply and newcomers get merged."],
  ["Your trail", "We follow your commits and PRs over time and suggest the next, slightly harder step."],
];

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-10 px-6 py-24">
      <div className="flex flex-col gap-4">
        <p className="font-mono text-sm text-muted">breadcrumbs</p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Follow the trail from issue to merged PR.
        </h1>
        <p className="max-w-xl text-lg text-ink-2">
          Enter your GitHub username. Get open-source issues you can actually get merged, from your
          first PR to your next one.
        </p>
      </div>
      <UsernameForm />
      <ol className="grid gap-4 sm:grid-cols-3">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="rounded-xl border border-border bg-surface p-4">
            <p className="font-mono text-xs text-muted">0{i + 1}</p>
            <p className="mt-1 font-medium">{title}</p>
            <p className="mt-1 text-sm text-ink-2">{body}</p>
          </li>
        ))}
      </ol>
    </main>
  );
}
