"use client";

import { useRouter } from "next/navigation";
import { useSWRConfig } from "swr";

import { ApiError, api, issuePath, type Unavailable } from "@/lib/api";
import type { IssueCard, Matches, SkipRequest } from "@/lib/contracts";
import { useToast } from "../ui/Toast";

const UNDO_MS = 5000;

/** Pick, save and skip, with the caches and toasts kept in sync. */
export function useIssueActions(login: string) {
  const router = useRouter();
  const toast = useToast();
  const { mutate } = useSWRConfig();
  const matchesKey = ["matches", login];

  const setCard = (card: IssueCard) =>
    mutate(matchesKey, (m?: Matches) => m && { ...m, issues: m.issues.map((i) => (i.id === card.id ? card : i)) }, {
      revalidate: false,
    });

  return {
    /** Returns the reason if the issue was taken since it was shown. */
    async pick(card: IssueCard, force = false): Promise<Unavailable | null> {
      try {
        await api.pick(login, card.id, force);
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) return e.detail as Unavailable;
        throw e;
      }
      await Promise.all([
        mutate(["attempts", login]),
        mutate(["trail-graph", login]),
        mutate(matchesKey, (m?: Matches) => m && { ...m, issues: m.issues.filter((i) => i.id !== card.id) }, {
          revalidate: false,
        }),
      ]);
      toast({ message: `Added ${card.repo}#${card.number} to your trail` });
      router.push(`/trail/${issuePath(card.id)}`);
      return null;
    },

    async toggleSave(card: IssueCard) {
      const next = { ...card, saved: !card.saved };
      setCard(next);
      mutate(["issue", card.id, login], (d?: { card: IssueCard }) => d && { ...d, card: next }, { revalidate: false });
      if (next.saved) await api.save(login, next);
      else await api.unsave(login, card.id);
      mutate(["saved", login]);
      toast({ message: next.saved ? "Saved for later" : "Removed from saved" });
    },

    /** Hide now; only tell the server after the undo window passes. */
    skip(card: IssueCard, reason: SkipRequest["reason"], onUndo?: () => void) {
      let previous: Matches | undefined;
      mutate(
        matchesKey,
        (m?: Matches) => {
          previous = m;
          return m && { ...m, issues: m.issues.filter((i) => i.id !== card.id) };
        },
        { revalidate: false },
      );
      const timer = setTimeout(() => api.skip(login, card.id, reason).catch(() => {}), UNDO_MS);
      toast({
        message: `Skipped ${card.repo}#${card.number}`,
        action: {
          label: "Undo",
          run: () => {
            clearTimeout(timer);
            mutate(matchesKey, previous, { revalidate: false });
            onUndo?.();
          },
        },
      });
    },
  };
}
