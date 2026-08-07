import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type Theme } from "@/hooks/useTheme";
import { cn } from "@/lib/cn";

const OPTIONS: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-line bg-surface p-0.5">
      {OPTIONS.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          aria-pressed={theme === value}
          onClick={() => setTheme(value)}
          className={cn(
            "grid size-7 place-items-center rounded-md transition-colors duration-fast",
            theme === value
              ? "bg-accent-soft text-accent"
              : "text-text-muted hover:text-text-secondary",
          )}
        >
          <Icon className="size-4" />
        </button>
      ))}
    </div>
  );
}
