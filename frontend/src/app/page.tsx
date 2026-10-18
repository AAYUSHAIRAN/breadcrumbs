import { GraphView } from "@/components/graph/GraphView";
import { LandingCta } from "@/components/LandingCta";
import type { GraphView as View } from "@/lib/contracts";

const STEPS = [
  ["Your skills", "Read from your public repos, dependency files and the PRs you've had merged elsewhere."],
  ["Issues you can land", "Unclaimed issues in active repos where maintainers reply and newcomers get merged."],
  ["Your trail", "We follow your commits and PRs over time and suggest the next, slightly harder step."],
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
        <p className="font-mono text-sm text-muted">breadcrumbs</p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">Follow the trail from issue to merged PR.</h1>
        <p className="max-w-2xl text-lg text-ink-2">
          Open-source issues you can actually get merged, matched to what you know, with the path through the code to the fix. From
          your first PR to your next one.
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

      <ol className="grid gap-4 sm:grid-cols-3">
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
