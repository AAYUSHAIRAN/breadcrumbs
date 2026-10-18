"""Graph views for the UI. Each returns the Cypher that produced it, shown under
the drawing, so it's verifiable that the picture is a real graph query.
"""

from app.contracts import GraphEdge, GraphNode, GraphView
from app.graph.progress import _rows

WHY_CYPHER = """MATCH (u:User {login: $login}), (i:Issue {id: $issue})-[:IN]->(r:Repo)
OPTIONAL MATCH (i)-[:NEEDS]->(t:Tech)
OPTIONAL MATCH (u)-[k:KNOWS]->(t)
OPTIONAL MATCH (u)-[:WORKING_ON]->(:Attempt)-[:FOR]->(past:Issue)-[:IN]->(r)
  WHERE past.id <> i.id
RETURN u.login, u.name, t.name, k.level, i.id, i.title, i.difficulty,
       r.name, r.stars, r.reply_hours, r.newcomer_merges_90d,
       collect(DISTINCT past.id)"""

TRAIL_CYPHER = """MATCH (u:User {login: $login})
OPTIONAL MATCH (u)-[:WORKING_ON]->(a:Attempt)-[:FOR]->(i:Issue)-[:IN]->(r:Repo)
OPTIONAL MATCH (i)-[:NEEDS]->(t:Tech)
WITH u, collect(DISTINCT {issue: i.id, title: i.title, status: a.status, repo: r.name, tech: t.name}) AS work
OPTIONAL MATCH (u)-[k:KNOWS]->(s:Tech)
WITH u, work, s, k ORDER BY k.level DESC
WITH u, work, collect({tech: s.name, level: k.level}) AS skills
OPTIONAL MATCH (u)-[:LEARNED]->(l:Tech)
RETURN u.login, u.name, work, skills[..6], collect(l.name)"""


def _hours(h: float) -> str:
    return "under an hour" if h < 1 else f"~{round(h)}h" if h < 48 else f"~{round(h / 24)} days"


def _short(issue_id: str) -> str:
    return "#" + issue_id.rsplit("#", 1)[-1]


async def why_path(login: str, issue_id: str) -> GraphView | None:
    """B5: You ─KNOWS─▶ Tech ◀─NEEDS─ Issue ─IN─▶ Repo, plus what we know about the repo."""
    rows = await _rows(WHY_CYPHER, {"login": login, "issue": issue_id})
    if not rows:
        return None
    (login, name, tech, level, iid, title, _difficulty, repo, stars, reply, newcomers, past) = rows[0]

    nodes = [
        GraphNode(id="user", kind="user", label=name or login, detail=f"@{login}"),
        GraphNode(id="issue", kind="issue", label=_short(iid), detail=title or ""),
        GraphNode(id="repo", kind="repo", label=repo, detail=f"★ {stars:,}" if stars else ""),
    ]
    edges = [GraphEdge(source="issue", target="repo", label="IN")]
    if tech:
        label = f"{tech} · {round(level * 100)}" if level is not None else tech
        nodes.append(GraphNode(id="tech", kind="tech", label=label, detail="your skill level, 0–100"))
        edges.append(GraphEdge(source="issue", target="tech", label="NEEDS"))
        if level is not None:
            edges.append(GraphEdge(source="user", target="tech", label="KNOWS"))
    if reply is not None:
        nodes.append(GraphNode(id="reply", kind="fact", label=f"replies in {_hours(reply)}", detail="median, recent PRs"))
        edges.append(GraphEdge(source="repo", target="reply", label=""))
    if newcomers:
        nodes.append(GraphNode(id="newcomers", kind="fact", label=f"{newcomers} newcomers merged", detail="last 90 days"))
        edges.append(GraphEdge(source="repo", target="newcomers", label=""))
    for p in past:
        nodes.append(GraphNode(id=f"past:{p}", kind="issue", label=_short(p), detail="you worked on this"))
        edges += [
            GraphEdge(source="user", target=f"past:{p}", label="WORKED_ON"),
            GraphEdge(source=f"past:{p}", target="repo", label="IN"),
        ]
    return GraphView(nodes=nodes, edges=edges, cypher=WHY_CYPHER)


async def trail_graph(login: str) -> GraphView | None:
    """F3: you → your strongest skills, your attempts → their repos and tech, and what you learned."""
    rows = await _rows(TRAIL_CYPHER, {"login": login})
    if not rows:
        return None
    login, name, work, skills, learned = rows[0]

    nodes: dict[str, GraphNode] = {"user": GraphNode(id="user", kind="user", label=name or login, detail=f"@{login}")}
    edges: list[GraphEdge] = []

    def tech(t: str, level: float | None = None) -> str:
        # The level goes on the node, not the edge: many KNOWS edges meet at "you" and their labels would pile up.
        label = f"{t} · {round(level * 100)}" if level is not None else t
        nodes.setdefault(f"tech:{t}", GraphNode(id=f"tech:{t}", kind="tech", label=label, detail="skill level 0–100"))
        return f"tech:{t}"

    for s in skills:
        if s["tech"]:
            edges.append(GraphEdge(source="user", target=tech(s["tech"], s["level"]), label=""))
    for w in work:
        if not w["issue"]:
            continue
        iid = f"issue:{w['issue']}"
        nodes[iid] = GraphNode(id=iid, kind="issue", label=_short(w["issue"]), detail=w["title"] or "")
        nodes.setdefault(f"repo:{w['repo']}", GraphNode(id=f"repo:{w['repo']}", kind="repo", label=w["repo"]))
        edges += [
            GraphEdge(source="user", target=iid, label=(w["status"] or "").replace("_", " ")),
            GraphEdge(source=iid, target=f"repo:{w['repo']}", label="IN"),
        ]
        if w["tech"]:
            edges.append(GraphEdge(source=iid, target=tech(w["tech"]), label="NEEDS"))
    for t in learned:
        edges.append(GraphEdge(source="user", target=tech(t), label="LEARNED"))
    return GraphView(nodes=list(nodes.values()), edges=edges, cypher=TRAIL_CYPHER)
