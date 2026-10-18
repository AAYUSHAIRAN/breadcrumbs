import { Suspense } from "react";

import { Onboarding } from "@/components/screens/Onboarding";

export default function StartPage() {
  return (
    <Suspense>
      <Onboarding />
    </Suspense>
  );
}
