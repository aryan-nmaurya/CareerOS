import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";

function Placeholder({ title }: { title: string }) {
  return (
    <AppShell>
      <TopBar title={title} subtitle="Coming in a later plan." />
    </AppShell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Placeholder title="Dashboard" />} />
      <Route path="/roadmap" element={<Placeholder title="Roadmap" />} />
      <Route path="/interview" element={<Placeholder title="Interviews" />} />
      <Route path="/settings" element={<Placeholder title="Settings" />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
