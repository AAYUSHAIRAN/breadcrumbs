import { Suspense } from "react";

import { UserView } from "@/components/UserView";

// The page is a static shell; UserView fetches from the API in the browser.
export default function UserPage() {
  return (
    <Suspense>
      <UserView />
    </Suspense>
  );
}
