import { Award, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { Assessment } from "@/types";

const LEVEL_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export function ResultSummary({ assessment }: { assessment: Assessment }) {
  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text-secondary">Your score</p>
            <p className="text-4xl font-semibold text-text-primary">
              {Math.round(assessment.score ?? 0)}
              <span className="text-lg text-text-secondary">/100</span>
            </p>
          </div>
          {assessment.estimated_level && (
            <span className="flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1.5 text-sm font-medium text-accent">
              <Award className="size-4" />
              {LEVEL_LABEL[assessment.estimated_level]}
            </span>
          )}
        </div>
        {assessment.summary && (
          <p className="text-sm text-text-secondary">{assessment.summary}</p>
        )}
      </Card>

      {(assessment.strengths.length > 0 || assessment.weaknesses.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {assessment.strengths.length > 0 && (
            <Card>
              <CardTitle className="flex items-center gap-1.5 text-success">
                <TrendingUp className="size-4" /> Strengths
              </CardTitle>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {assessment.strengths.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Card>
          )}
          {assessment.weaknesses.length > 0 && (
            <Card>
              <CardTitle className="flex items-center gap-1.5 text-danger">
                <TrendingDown className="size-4" /> Needs work
              </CardTitle>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {assessment.weaknesses.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Question breakdown</h3>
        {assessment.questions.map((question, index) => (
          <Card key={question.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-text-primary">
                Question {index + 1}
              </span>
              <span
                className={cn(
                  "text-sm font-semibold",
                  (question.score ?? 0) >= 7
                    ? "text-success"
                    : (question.score ?? 0) >= 4
                      ? "text-warning"
                      : "text-danger",
                )}
              >
                {question.score ?? 0}/10
              </span>
            </div>
            <p className="text-sm text-text-primary">{question.question}</p>
            <CardDescription>
              Your answer:{" "}
              {question.type === "mcq" && question.options && question.user_answer !== null
                ? question.options[Number(question.user_answer)]
                : question.user_answer || "Not answered"}
            </CardDescription>
            {question.type === "mcq" &&
              question.correct_option !== null &&
              question.options && (
                <CardDescription>
                  Correct answer: {question.options[question.correct_option]}
                </CardDescription>
              )}
            {question.ai_feedback && (
              <CardDescription className="text-text-primary">
                {question.ai_feedback}
              </CardDescription>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
