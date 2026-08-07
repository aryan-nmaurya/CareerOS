import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useProfile, useUpdateProfile } from "@/hooks/useProfile";

export default function SettingsPage() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const [name, setName] = useState("");

  useEffect(() => {
    if (profile) setName(profile.name);
  }, [profile]);

  const trimmed = name.trim();
  const dirty = Boolean(trimmed) && trimmed !== profile?.name;

  return (
    <AppShell>
      <TopBar title="Settings" subtitle="Your profile and appearance." />

      <Card className="max-w-md">
        <CardTitle>Your name</CardTitle>
        <CardDescription className="mt-1">
          Used across your dashboard and reports.
        </CardDescription>

        <div className="mt-4 flex gap-2">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={120}
            aria-label="Your name"
          />
          <Button
            disabled={!dirty || updateProfile.isPending}
            onClick={() => updateProfile.mutate({ name: trimmed })}
          >
            Save
          </Button>
        </div>
      </Card>
    </AppShell>
  );
}
