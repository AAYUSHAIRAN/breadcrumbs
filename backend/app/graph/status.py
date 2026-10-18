"""Attempt status machine.

selected → in_progress → pr_open → in_review ⇄ changes_requested → merged
                                        any open state → closed | abandoned
"""

from app.contracts import AttemptStatus, EventType

TERMINAL: set[AttemptStatus] = {"merged", "closed", "abandoned"}


def next_status(current: AttemptStatus, event: EventType) -> AttemptStatus:
    if current in TERMINAL:
        return current

    match event:
        case "commit":
            if current == "selected":
                return "in_progress"
            if current == "changes_requested":
                return "in_review"  # pushed fixes (E4)
            return current
        case "pr_opened":
            return "pr_open"
        case "review_commented" | "approved":
            return "in_review"
        case "changes_requested":
            return "changes_requested"
        case "merged":
            return "merged"
        case "pr_closed" | "issue_closed":
            return "closed"
        case "abandoned":
            return "abandoned"
        case "selected":
            return current
