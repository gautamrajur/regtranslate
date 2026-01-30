"""Cross-regulation deduplication of extracted tasks via semantic similarity."""

from __future__ import annotations

from typing import Any

from app.models.schemas import ExtractionTask
from app.services import embeddings

PRIORITY_ORDER = {"High": 3, "Medium": 2, "Low": 1}
SIM_THRESHOLD = 0.85


def _cosine_sim(a: list[float], b: list[float]) -> float:
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _merge_tasks(cluster: list[ExtractionTask]) -> ExtractionTask:
    """Merge a cluster into one task: highest priority, merged also_satisfies, combined acceptance criteria and subtasks."""
    from app.models.schemas import ExtractionSubtask

    best = max(cluster, key=lambda t: PRIORITY_ORDER.get(t.priority, 0))
    all_satisfies: set[str] = set()
    for t in cluster:
        all_satisfies.add(t.source_citation)
        all_satisfies.update(t.also_satisfies)
    all_satisfies.discard(best.source_citation)
    ac: list[str] = []
    seen: set[str] = set()
    for t in cluster:
        for c in t.acceptance_criteria:
            n = c.strip().lower()
            if n and n not in seen:
                seen.add(n)
                ac.append(c.strip())
    if not ac and cluster:
        ac = list(cluster[0].acceptance_criteria)
    # Merge subtasks: dedupe by title, prefer best's subtasks first
    subtasks: list[ExtractionSubtask] = []
    seen_titles: set[str] = set()
    for t in [best] + [x for x in cluster if x is not best]:
        for st in t.subtasks:
            key = st.title.strip().lower()
            if key and key not in seen_titles:
                seen_titles.add(key)
                subtasks.append(st)
    return ExtractionTask(
        task_id=best.task_id,
        title=best.title,
        description=best.description,
        priority=best.priority,
        penalty_risk=best.penalty_risk,
        source_citation=best.source_citation,
        source_text=best.source_text,
        responsible_role=best.responsible_role,
        acceptance_criteria=ac,
        also_satisfies=sorted(all_satisfies),
        confidence=best.confidence,
        subtasks=subtasks,
    )


def deduplicate(tasks: list[ExtractionTask], threshold: float = SIM_THRESHOLD) -> list[ExtractionTask]:
    """
    Cluster tasks by semantic similarity (description embeddings), merge clusters.

    Uses threshold (default 0.85). Returns merged list; each merged task has
    also_satisfies filled from other cluster members' source_citation.
    """
    if len(tasks) <= 1:
        return list(tasks)

    texts = [t.description for t in tasks]
    vecs = embeddings.embed_texts(texts)
    n = len(tasks)
    parent = list(range(n))

    def find(i: int) -> int:
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine_sim(vecs[i], vecs[j]) >= threshold:
                union(i, j)

    clusters: dict[int, list[ExtractionTask]] = {}
    for i in range(n):
        p = find(i)
        clusters.setdefault(p, []).append(tasks[i])

    return [_merge_tasks(cl) for cl in clusters.values()]
