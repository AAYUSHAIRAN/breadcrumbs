import { GraphView } from "@/components/graph/GraphView";
import { LandingCta } from "@/components/LandingCta";
import type { GraphView as View } from "@/lib/contracts";

const STEPS = [
  ["Your skills", "Read from your public repos, dependency files and the PRs you've had merged elsewhere."],
  ["Issues you can land", "Unclaimed issues in active repos where maintainers reply and newcomers get merged."],
  ["✨ Guide writes the hard part", "Our AI agent writes your claim comment, setup commands and PR, following the repo's own rules."],
  ["Your trail", "Your progress lives in a graph, so every next step builds on the last."],
];

// What the Guide agent does on every run, in order. Mirrors its agent trace.
const GUIDE_STEPS = [
  ["Reads your profile", "Skills, level and the time you have, from your graph"],
  ["Recalls what it remembers", "Notes it saved about you in earlier sessions"],
  ["Recalls what it learned about the repo", "Facts earlier runs saved, from anyone working there"],
  ["Reads the repo's rules", "CONTRIBUTING, PR template, package scripts and CI, live from GitHub"],
  ["Writes your drafts", "Claim comment, exact setup commands, PR description in the repo's template"],
  ["Remembers for next time", "Saves what it learned back to the graph, citing the file"],
];

// An illustrative path, the same shape as the real one on every issue page.
const EXAMPLE: View = {
  nodes: [
    { id: "user", kind: "user", label: "You", detail: "" },
    { id: "tech", kind: "tech", label: "javascript · 93", detail: "" },
    { id: "issue", kind: "issue", label: "#12107", detail: "Irrelevant error message" },
    { id: "repo", kind: "repo", label: "CesiumGS/cesium", detail: "" },
    { id: "reply", kind: "fact", label: "replies in ~13h", detail: "" },
    { id: "newcomers", kind: "fact", label: "7 newcomers merged", detail: "" },
  ],
  edges: [
    { source: "user", target: "tech", label: "KNOWS" },
    { source: "issue", target: "tech", label: "NEEDS" },
    { source: "issue", target: "repo", label: "IN" },
    { source: "repo", target: "reply", label: "" },
    { source: "repo", target: "newcomers", label: "" },
  ],
  cypher: `MATCH (u:User {login: $login})-[k:KNOWS]->(t:Tech)<-[:NEEDS]-(i:Issue)-[:IN]->(r:Repo)
RETURN u, k, t, i, r`,
};

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-16 px-6 py-20">
      <section className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center gap-3">
          <p className="font-mono text-sm text-muted">breadcrumbs</p>
          <span className="rounded-full border border-accent bg-info-bg px-3 py-1 text-xs font-medium">
            ✨ AI agent with graph memory · FalkorDB + Claude
          </span>
        </div>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">Follow the trail from issue to merged PR.</h1>
        <p className="max-w-2xl text-lg text-ink-2">
          Open-source issues you can actually get merged, matched to what you know. Then <strong className="font-medium text-ink">Guide</strong>, our
          AI agent, writes everything you need to land the fix, using what your graph knows about you and the repo&apos;s own rules.
        </p>
        <LandingCta />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Every match is a path in your graph</h2>
        <p className="max-w-2xl text-sm text-ink-2">
          Not a keyword search: we follow what you know to issues that need it, in repos that treat newcomers well. This is an
          example; yours is built from your GitHub.
        </p>
        <GraphView view={EXAMPLE} title="Example: the graph path from you to an issue" />
      </section>

      <section className="flex flex-col gap-4 rounded-2xl border border-accent bg-info-bg p-6 sm:p-8">
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-accent-strong">Meet Guide, the agent inside Breadcrumbs</p>
          <h2 className="text-2xl font-semibold tracking-tight">It knows you, it reads the rules, and it remembers.</h2>
          <p className="max-w-2xl text-sm text-ink-2">
            Finding the right issue is half the job. Newcomers still get stuck on how to claim it, set it up and write the PR. Guide
            does that for you, with FalkorDB as its context and memory, and shows every step and query it ran.
          </p>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {GUIDE_STEPS.map(([title, body], i) => (
            <li key={title} className="rounded-xl border border-border bg-surface p-4">
              <p className="font-mono text-xs text-muted">step {i + 1}</p>
              <p className="mt-1 font-medium">{title}</p>
              <p className="mt-1 text-sm text-ink-2">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="rounded-xl border border-border bg-surface p-5">
            <p className="font-mono text-xs text-muted">0{i + 1}</p>
            <p className="mt-1 font-medium">{title}</p>
            <p className="mt-1 text-sm text-ink-2">{body}</p>
          </li>
        ))}
      </ol>
    </main>
  );
}
