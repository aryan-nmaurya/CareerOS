import type { ReactNode } from "react";

import { Sidebar } from "@/components/layout/Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-bg">
      <Sidebar />
      {/* pb-24 clears the fixed bottom nav on mobile. */}
      <main className="mx-auto w-full max-w-5xl px-5 pb-24 pt-8 md:px-8 md:pb-8">
        {children}
      </main>
    </div>
  );
}
