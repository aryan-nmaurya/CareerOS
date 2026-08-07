import { Textarea } from "@/components/ui/textarea";

interface DescriptiveAnswerProps {
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
}

export function DescriptiveAnswer({ value, onChange, onBlur }: DescriptiveAnswerProps) {
  return (
    <Textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onBlur={onBlur}
      placeholder="Type your answer…"
      aria-label="Your answer"
    />
  );
}
