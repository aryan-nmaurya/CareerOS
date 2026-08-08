import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="grid place-items-center py-24 text-sm text-text-muted">
      <Loader2 className="mb-2 size-5 animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="space-y-3">
      <CardTitle>Something went wrong</CardTitle>
      <CardDescription>{message}</CardDescription>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="size-4" /> Try again
        </Button>
      )}
    </Card>
  );
}
