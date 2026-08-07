interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function ProgressRing({ percent, size = 80, strokeWidth = 8, label }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, percent));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          className="fill-none stroke-line"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="fill-none stroke-accent transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-lg font-semibold text-text-primary">{Math.round(clamped)}%</span>
        {label && <span className="text-[10px] text-text-muted">{label}</span>}
      </div>
    </div>
  );
}
