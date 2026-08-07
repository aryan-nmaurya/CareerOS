import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import type { AssessmentQuestion } from "@/types";

interface QuestionCardProps {
  question: AssessmentQuestion;
  index: number;
  total: number;
  children: ReactNode;
}

export function QuestionCard({ question, index, total, children }: QuestionCardProps) {
  return (
    <Card className="space-y-5">
      <div className="flex items-center justify-between text-sm text-text-secondary">
        <span>
          Question {index + 1} of {total}
        </span>
        <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">
          {question.topic_tag}
        </span>
      </div>
      <p className="text-lg font-medium text-text-primary">{question.question}</p>
      {children}
    </Card>
  );
}
