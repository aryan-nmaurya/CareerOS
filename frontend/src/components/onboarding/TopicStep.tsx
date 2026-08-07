import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PRESET_TOPICS } from "@/lib/constants";
import { cn } from "@/lib/cn";

export function TopicStep({ onNext }: { onNext: (topic: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [custom, setCustom] = useState("");

  const topic = (custom.trim() || selected) ?? "";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (topic) onNext(topic);
      }}
      className="space-y-6"
    >
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          What do you want to learn?
        </h2>
        <p className="text-text-secondary">
          Pick one, or type anything else you have in mind.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {PRESET_TOPICS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={selected === preset && !custom.trim()}
            onClick={() => {
              setSelected(preset);
              setCustom("");
            }}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-fast",
              selected === preset && !custom.trim()
                ? "border-accent bg-accent-soft text-accent"
                : "border-line bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary",
            )}
          >
            {preset}
          </button>
        ))}
      </div>

      <Input
        value={custom}
        onChange={(event) => setCustom(event.target.value)}
        placeholder="Or something else — e.g. Rust, Systems Design"
        maxLength={120}
        aria-label="Custom topic"
      />

      <Button type="submit" size="lg" disabled={!topic}>
        Continue <ArrowRight className="size-4" />
      </Button>
    </form>
  );
}
