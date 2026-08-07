import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useActiveTrack, useProfile } from "@/hooks/useProfile";

export default function DashboardPage() {
  const { data: profile } = useProfile();
  const { data: track } = useActiveTrack();

  return (
    <AppShell>
      <TopBar
        title={`Welcome back, ${profile?.name ?? "there"}`}
        subtitle={
          track
            ? `You're learning ${track.topic} at ${track.experience_level} level.`
            : "Pick something to learn to get started."
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardTitle>Current track</CardTitle>
          <CardDescription className="mt-1">
            {track ? track.topic : "No active track yet."}
          </CardDescription>
          <Link to="/onboarding" className="mt-4 inline-block">
            <Button variant="secondary" size="sm">
              <Plus className="size-4" /> New track
            </Button>
          </Link>
        </Card>

        <Card>
          <CardTitle>Roadmap</CardTitle>
          <CardDescription className="mt-1">
            Your personalized roadmap arrives in the next build stage.
          </CardDescription>
        </Card>
      </div>
    </AppShell>
  );
}
