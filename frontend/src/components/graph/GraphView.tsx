"use client";

import { useMemo, useState } from "react";

import type { GraphNode, GraphView as View } from "@/lib/contracts";

type Kind = GraphNode["kind"];

const NODE_W = 148;
const NODE_H = 50;
const COL_GAP = 46;
const ROW_GAP = 16;
const PAD = 14;
const MAX_LABEL = 19;

const KIND_CAPTION: Record<Kind, string> = { user: "you", tech: "skill", issue: "issue", repo: "repo", fact: "fact" };

// Identity is carried by the caption and shape, not colour alone.
const KIND_STYLE: Record<Kind, { fill: string; stroke: string; text: string; caption: string; dash?: string }> = {
  user: { fill: "var(--accent-strong)", stroke: "var(--accent-strong)", text: "#ffffff", caption: "rgba(255,255,255,0.75)" },
  tech: { fill: "var(--info-bg)", stroke: "var(--accent)", text: "var(--ink)", caption: "var(--ink-2)" },
  issue: { fill: "var(--surface)", stroke: "var(--accent)", text: "var(--ink)", caption: "var(--ink-2)" },
  repo: { fill: "var(--surface)", stroke: "var(--hairline)", text: "var(--ink)", caption: "var(--ink-2)" },
  fact: { fill: "var(--good-bg)", stroke: "var(--good-bg)", text: "var(--good)", caption: "var(--good)", dash: "4 3" },
};

const truncate = (s: string) => (s.length > MAX_LABEL ? `${s.slice(0, MAX_LABEL - 1)}…` : s);

interface Placed extends GraphNode {
  x: number;
  y: number;
}

type Direction = "horizontal" | "vertical";
const LEVEL_GAP_V = 46; // vertical gap between levels in the vertical layout

/** Nodes are placed in levels (columns, or rows when vertical) by kind; deterministic, no physics. */
function layout(view: View, levelOf: Record<Kind, number>, direction: Direction) {
  const byLevel = new Map<number, GraphNode[]>();
  for (const n of view.nodes) {
    const level = levelOf[n.kind];
    byLevel.set(level, [...(byLevel.get(level) ?? []), n]);
  }
  const levels = [...byLevel.keys()].sort((a, b) => a - b);
  const widest = Math.max(...[...byLevel.values()].map((ns) => ns.length));
  const placed = new Map<string, Placed>();

  if (direction === "horizontal") {
    const height = PAD * 2 + widest * NODE_H + (widest - 1) * ROW_GAP;
    levels.forEach((level, li) => {
      const nodes = byLevel.get(level)!;
      const span = nodes.length * NODE_H + (nodes.length - 1) * ROW_GAP;
      nodes.forEach((n, i) =>
        placed.set(n.id, { ...n, x: PAD + li * (NODE_W + COL_GAP), y: (height - span) / 2 + i * (NODE_H + ROW_GAP) }),
      );
    });
    return { placed, width: PAD * 2 + levels.length * NODE_W + (levels.length - 1) * COL_GAP, height };
  }

  const width = PAD * 2 + widest * NODE_W + (widest - 1) * ROW_GAP;
  levels.forEach((level, li) => {
    const nodes = byLevel.get(level)!;
    const span = nodes.length * NODE_W + (nodes.length - 1) * ROW_GAP;
    nodes.forEach((n, i) =>
      placed.set(n.id, { ...n, x: (width - span) / 2 + i * (NODE_W + ROW_GAP), y: PAD + li * (NODE_H + LEVEL_GAP_V) }),
    );
  });
  return { placed, width, height: PAD * 2 + levels.length * NODE_H + (levels.length - 1) * LEVEL_GAP_V };
}

/** Room for an edge label between two nodes; labels that don't fit are left to the list view. */
function labelRoom(a: Placed, b: Placed, direction: Direction) {
  if (direction === "vertical") return a.y === b.y ? Infinity : LEVEL_GAP_V * 4;
  return a.x === b.x ? Infinity : Math.abs(a.x - b.x) - NODE_W;
}

const labelWidth = (label: string) => label.length * 6.6 + 12;

function edgePath(a: Placed, b: Placed, direction: Direction) {
  if (direction === "vertical") {
    const ax = a.x + NODE_W / 2;
    const bx = b.x + NODE_W / 2;
    if (a.y === b.y) {
      const y = a.y + NODE_H;
      return { d: `M${ax},${y} C${ax},${y + 30} ${bx},${y + 30} ${bx},${y}`, mx: (ax + bx) / 2, my: y + 22 };
    }
    const down = a.y < b.y;
    const y1 = down ? a.y + NODE_H : a.y;
    const y2 = down ? b.y : b.y + NODE_H;
    const dy = (y2 - y1) / 2;
    return { d: `M${ax},${y1} C${ax},${y1 + dy} ${bx},${y2 - dy} ${bx},${y2}`, mx: (ax + bx) / 2, my: (y1 + y2) / 2 };
  }
  const ay = a.y + NODE_H / 2;
  const by = b.y + NODE_H / 2;
  if (a.x === b.x) {
    // Same column: loop out to the right.
    const x = a.x + NODE_W;
    return { d: `M${x},${ay} C${x + 40},${ay} ${x + 40},${by} ${x},${by}`, mx: x + 30, my: (ay + by) / 2 };
  }
  const forward = a.x < b.x;
  const x1 = forward ? a.x + NODE_W : a.x;
  const x2 = forward ? b.x : b.x + NODE_W;
  const dx = (x2 - x1) / 2;
  return { d: `M${x1},${ay} C${x1 + dx},${ay} ${x2 - dx},${by} ${x2},${by}`, mx: (x1 + x2) / 2, my: (ay + by) / 2 };
}

const DEFAULT_COLUMNS: Record<Kind, number> = { user: 0, tech: 1, issue: 2, repo: 3, fact: 4 };

export function GraphView({
  view,
  levels = DEFAULT_COLUMNS,
  direction = "horizontal",
  title,
}: {
  view: View;
  levels?: Record<Kind, number>;
  direction?: Direction;
  title: string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const { placed, width, height } = useMemo(() => layout(view, levels, direction), [view, levels, direction]);
  const edges = view.edges.filter((e) => placed.has(e.source) && placed.has(e.target));

  return (
    <figure className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label={title} className="mx-auto">
          <style>{`
            @keyframes draw { from { stroke-dashoffset: 400 } to { stroke-dashoffset: 0 } }
            @keyframes appear { from { opacity: 0 } to { opacity: 1 } }
            .bc-edge { stroke-dasharray: 400; animation: draw 700ms ease-out both; }
            .bc-fade { animation: appear 400ms ease-out both; }
            @media (prefers-reduced-motion: reduce) { .bc-edge, .bc-fade { animation: none; stroke-dasharray: none; } }
          `}</style>
          {edges.map((e, i) => {
            const [a, b] = [placed.get(e.source)!, placed.get(e.target)!];
            const { d, mx, my } = edgePath(a, b, direction);
            const showLabel = e.label && labelWidth(e.label) <= labelRoom(a, b, direction) - 4;
            const lit = hover === null || hover === e.source || hover === e.target;
            return (
              <g key={`${e.source}-${e.target}-${e.label}`} opacity={lit ? 1 : 0.2} style={{ transition: "opacity 150ms" }}>
                <path d={d} fill="none" stroke="var(--accent)" strokeWidth={2} className="bc-edge" style={{ animationDelay: `${i * 160}ms` }} />
                <title>{`${a.label} ${e.label || "→"} ${b.label}`}</title>
                {showLabel && <g className="bc-fade" style={{ animationDelay: `${i * 160 + 350}ms` }}>
                  <rect x={mx - labelWidth(e.label) / 2} y={my - 9} width={labelWidth(e.label)} height={18} rx={9} fill="var(--surface)" stroke="var(--hairline)" />
                  <text x={mx} y={my + 4} textAnchor="middle" fontSize={10.5} fill="var(--ink-2)" fontFamily="var(--font-geist-mono)">
                    {e.label}
                  </text>
                </g>}
              </g>
            );
          })}
          {[...placed.values()].map((n, i) => {
            const s = KIND_STYLE[n.kind];
            return (
              <g
                key={n.id}
                transform={`translate(${n.x},${n.y})`}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
                className="bc-fade cursor-default"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <title>{n.detail ? `${n.label} — ${n.detail}` : n.label}</title>
                <rect width={NODE_W} height={NODE_H} rx={n.kind === "user" ? 25 : 10} fill={s.fill} stroke={s.stroke} strokeWidth={hover === n.id ? 2.5 : 1.5} strokeDasharray={s.dash} />
                <text x={12} y={18} fontSize={9.5} fill={s.caption} style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  {KIND_CAPTION[n.kind]}
                </text>
                <text x={12} y={36} fontSize={13} fontWeight={500} fill={s.text}>
                  {truncate(n.label)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="flex flex-wrap gap-4 text-xs text-ink-2">
        <details>
          <summary className="cursor-pointer hover:text-ink">See the query</summary>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-page p-3 font-mono text-[11px] leading-relaxed text-ink">{view.cypher}</pre>
        </details>
        <details>
          <summary className="cursor-pointer hover:text-ink">View as list</summary>
          <ul className="mt-2 flex flex-col gap-1 font-mono">
            {edges.map((e) => (
              <li key={`${e.source}-${e.target}-${e.label}`}>
                {placed.get(e.source)!.label} —{e.label || "→"}→ {placed.get(e.target)!.label}
              </li>
            ))}
          </ul>
        </details>
      </figcaption>
    </figure>
  );
}
