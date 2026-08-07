import { cn } from "@/lib/cn";

interface McqOptionsProps {
  options: string[];
  selected: number | null;
  onSelect: (index: number) => void;
}

export function McqOptions({ options, selected, onSelect }: McqOptionsProps) {
  return (
    <div className="grid gap-2">
      {options.map((option, index) => (
        <button
          key={index}
          type="button"
          aria-pressed={selected === index}
          onClick={() => onSelect(index)}
          className={cn(
            "rounded-lg border px-4 py-3 text-left text-sm transition-colors duration-fast",
            selected === index
              ? "border-accent bg-accent-soft text-accent"
              : "border-line bg-surface text-text-primary hover:bg-surface-hover",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
