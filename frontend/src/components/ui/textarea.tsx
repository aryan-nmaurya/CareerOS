import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-32 w-full resize-y rounded-lg border border-line bg-surface px-3.5 py-3 text-sm",
        "text-text-primary placeholder:text-text-muted",
        "transition-colors duration-fast",
        "focus:border-accent focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}
