import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

interface TranscriptPanelProps {
  sttSupported: boolean;
  listening: boolean;
  liveTranscript: string;
  manualValue: string;
  onManualChange: (value: string) => void;
}

export function TranscriptPanel({
  sttSupported,
  listening,
  liveTranscript,
  manualValue,
  onManualChange,
}: TranscriptPanelProps) {
  if (!sttSupported) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-text-muted">
          Speech recognition unavailable in this browser — type your answer.
        </p>
        <Textarea
          value={manualValue}
          onChange={(e) => onManualChange(e.target.value)}
          rows={6}
          placeholder="Type your answer…"
        />
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            listening ? "animate-pulse bg-danger" : "bg-text-muted",
          )}
        />
        <p className="text-xs text-text-muted">{listening ? "Listening…" : "Not listening"}</p>
      </div>
      <p className="min-h-24 text-sm text-text-primary">
        {liveTranscript || "Start speaking — your words will appear here."}
      </p>
    </div>
  );
}
