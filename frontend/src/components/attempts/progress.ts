import type { Attempt, AttemptStatus, EventType } from "@/lib/contracts";

export const STEPS = ["Picked", "Coding", "PR open", "In review", "Merged"] as const;

const STEP_OF: Record<AttemptStatus, number> = {
  selected: 0,
  in_progress: 1,
  pr_open: 2,
  in_review: 3,
  changes_requested: 3,
  merged: 4,
  closed: -1,
  abandoned: -1,
};

export const stepOf = (status: AttemptStatus) => STEP_OF[status];
export const isActive = (a: Attempt) => STEP_OF[a.status] >= 0 && a.status !== "merged";

export const STATUS_LABEL: Record<AttemptStatus, string> = {
  selected: "Picked",
  in_progress: "Coding",
  pr_open: "PR open",
  in_review: "In review",
  changes_requested: "Changes requested",
  merged: "Merged 🎉",
  closed: "Closed",
  abandoned: "Abandoned",
};

export const EVENT_LABEL: Record<EventType, string> = {
  selected: "Picked this issue",
  commit: "Pushed a commit",
  pr_opened: "Opened a pull request",
  review_commented: "Got review comments",
  changes_requested: "Changes were requested",
  approved: "PR approved",
  merged: "PR merged",
  pr_closed: "PR closed without merging",
  issue_closed: "Issue was closed",
  abandoned: "Stopped working on it",
};

/** The one thing to do next, per status. */
export function nextStep(a: Attempt, number: string): { title: string; body: string } {
  switch (a.status) {
    case "selected":
      return { title: "Claim it", body: "Post a short comment so the maintainers know you're working on it. A draft is in the Guide below." };
    case "in_progress":
      return { title: "Open a pull request", body: `Put "Fixes #${number}" in the description so the issue links to it and we can follow it.` };
    case "pr_open":
      return { title: "Wait for a review", body: "Maintainers will look at your PR. Keep an eye on comments and CI." };
    case "in_review":
      return { title: "Respond to the review", body: "Reply to comments and push any follow-up commits." };
    case "changes_requested":
      return { title: "Push the requested changes", body: "Address each review comment, push, then re-request a review." };
    case "merged":
      return { title: "Merged. Nice work!", body: "Ready for something a little harder? Your next matches take this into account." };
    default:
      return { title: "This attempt is closed", body: "No penalty. Find another issue that fits." };
  }
}
