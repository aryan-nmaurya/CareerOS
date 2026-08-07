import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border border-line bg-surface px-3.5 text-sm",
        "text-text-primary placeholder:text-text-muted",
        "transition-colors duration-fast",
        "focus:border-accent focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}
