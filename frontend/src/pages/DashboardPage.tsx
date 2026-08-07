import { Loader2, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { ProgressRing } from "@/components/roadmap/ProgressRing";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useDashboard } from "@/hooks/useDashboard";

export default function DashboardPage() {
  const { data: dashboard, isPending } = useDashboard();
  const navigate = useNavigate();

  if (isPending || !dashboard) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  const { profile, active_track: track, next_module: nextModule } = dashboard;

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
          {dashboard.roadmap_summary ? (
            <>
              <CardDescription className="mt-1">{dashboard.roadmap_summary}</CardDescription>
              {dashboard.current_phase && (
                <p className="mt-2 text-xs font-medium text-accent">
                  Currently on: {dashboard.current_phase}
                </p>
              )}
            </>
          ) : (
            <CardDescription className="mt-1">
              {track ? "Not generated yet." : "Start a track to get one."}
            </CardDescription>
          )}
          {track && (
            <Button size="sm" className="mt-4" onClick={() => navigate("/roadmap")}>
              {dashboard.roadmap_summary ? "View roadmap" : "Generate roadmap"}
            </Button>
          )}
        </Card>
      </div>

      {dashboard.roadmap_summary && (
        <div className="mt-4 grid gap-4 sm:grid-cols-[auto_1fr]">
          <Card className="flex items-center justify-center">
            <ProgressRing percent={dashboard.completion_pct} label="complete" />
          </Card>

          <Card className="flex flex-col justify-center gap-1">
            <p className="text-sm text-text-primary">
              {dashboard.completed_modules} of{" "}
              {dashboard.completed_modules + dashboard.remaining_modules} modules done
            </p>
            {nextModule ? (
              <>
                <p className="text-xs text-text-secondary">Next up: {nextModule.title}</p>
                <Button
                  size="sm"
                  className="mt-2 self-start"
                  onClick={() => navigate("/roadmap")}
                >
                  Continue learning
                </Button>
              </>
            ) : (
              <p className="text-xs text-success">Roadmap complete — nice work.</p>
            )}
          </Card>
        </div>
      )}

      <Card className="mt-4">
        <CardTitle>Recent interviews</CardTitle>
        <CardDescription className="mt-1">
          {dashboard.recent_interviews.length === 0
            ? "No interviews yet."
            : `${dashboard.recent_interviews.length} completed.`}
        </CardDescription>
      </Card>
    </AppShell>
  );
}
