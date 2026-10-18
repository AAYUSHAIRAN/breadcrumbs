from app.graph.status import next_status


def fold(*events):
    status = "selected"
    for e in events:
        status = next_status(status, e)
    return status


def test_happy_path():
    assert fold("commit", "pr_opened", "review_commented", "approved", "merged") == "merged"


def test_changes_requested_then_fix_goes_back_to_review():
    assert fold("pr_opened", "changes_requested") == "changes_requested"
    assert fold("pr_opened", "changes_requested", "commit") == "in_review"


def test_commit_after_pr_does_not_regress():
    assert fold("commit", "pr_opened", "commit") == "pr_open"


def test_terminal_states_stick():
    assert fold("pr_opened", "merged", "issue_closed") == "merged"
    assert fold("abandoned", "commit") == "abandoned"


def test_closed_without_merge():
    assert fold("pr_opened", "pr_closed") == "closed"
