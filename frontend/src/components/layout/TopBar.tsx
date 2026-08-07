import { ThemeToggle } from "@/components/layout/ThemeToggle";

interface TopBarProps {
  title: string;
  subtitle?: string;
}

export function TopBar({ title, subtitle }: TopBarProps) {
  return (
    <header className="flex items-start justify-between gap-4 pb-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      <ThemeToggle />
    </header>
  );
}
