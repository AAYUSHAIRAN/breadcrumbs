import { Suspense } from "react";

import { RememberUser } from "@/components/shell/RememberUser";

// Shareable link: /u/<login> remembers the user and opens their home.
export default function UserLink() {
  return (
    <Suspense>
      <RememberUser />
    </Suspense>
  );
}
