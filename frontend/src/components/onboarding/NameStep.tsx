import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function NameStep({ onNext }: { onNext: (name: string) => void }) {
  const [name, setName] = useState("");
  const trimmed = name.trim();

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (trimmed) onNext(trimmed);
      }}
      className="space-y-6"
    >
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          What should we call you?
        </h2>
        <p className="text-text-secondary">
          CareerOS builds a plan around you, so let's start with a name.
        </p>
      </div>

      <Input
        autoFocus
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Your name"
        maxLength={120}
        aria-label="Your name"
      />

      <Button type="submit" size="lg" disabled={!trimmed}>
        Continue <ArrowRight className="size-4" />
      </Button>
    </form>
  );
}
