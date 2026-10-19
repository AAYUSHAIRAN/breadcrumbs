"use client";

import { useSWRConfig } from "swr";

import { api } from "@/lib/api";
import type { Attempt } from "@/lib/contracts";
import { useToast } from "../ui/Toast";

/** Remove an issue from the trail (asks first: it deletes the attempt's timeline). Resolves true if removed. */
export function useRemoveAttempt(login: string) {
  const { mutate } = useSWRConfig();
  const toast = useToast();
  return async (a: Pick<Attempt, "issue_id" | "issue_title">) => {
    if (
      !window.confirm(
        `Remove "${a.issue_title}" from your trail?\n\nIts progress and timeline will be deleted.`,
      )
    )
      return false;
    await api.removeAttempt(login, a.issue_id);
    await Promise.all([
      mutate(
        ["attempts", login],
        (all?: Attempt[]) => all?.filter((x) => x.issue_id !== a.issue_id),
        { revalidate: true },
      ),
      mutate(["trail-graph", login]),
      mutate(["matches", login]),
    ]);
    toast({ message: `Removed ${a.issue_id} from your trail` });
    return true;
  };
}
