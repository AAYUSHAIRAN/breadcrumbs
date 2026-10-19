import { Suspense } from "react";

import { OnboardingPage } from "@/components/screens/Onboarding";

export default function StartPage() {
  return (
    <Suspense>
      <OnboardingPage />
    </Suspense>
  );
}
