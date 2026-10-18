"""HR-specified precedence, not inferred policy or a semantic contradiction model."""

from datetime import date


def current_passages(chunks, today):
    current = [
        c
        for c in chunks
        if (not c.document.effective_from or c.document.effective_from <= today)
        and (not c.document.effective_until or c.document.effective_until >= today)
    ]
    best: dict[str, tuple[int, date]] = {}
    for chunk in current:
        doc = chunk.document
        if doc.policy_key:
            score = (doc.priority, doc.effective_from or date.min)
            best[doc.policy_key] = max(best.get(doc.policy_key, score), score)
    return [
        c
        for c in current
        if not c.document.policy_key
        or (c.document.priority, c.document.effective_from or date.min)
        == best[c.document.policy_key]
    ]


def ambiguous_policy(ranked, threshold):
    relevant_keys = {c.document.policy_key for c, coverage, _ in ranked if coverage >= threshold}
    groups: dict[str, set[int]] = {}
    for chunk, coverage, _ in ranked:
        doc = chunk.document
        if coverage >= threshold and doc.known_conflict:
            return True
        if doc.policy_key and doc.policy_key in relevant_keys:
            groups.setdefault(doc.policy_key, set()).add(doc.id)
    return any(len(ids) > 1 for ids in groups.values())
