import { Suspense } from "react";

import { AppFrame } from "@/components/shell/AppFrame";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense>
      <AppFrame>{children}</AppFrame>
    </Suspense>
  );
}
