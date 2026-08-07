import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DescriptiveAnswer } from "@/components/assessment/DescriptiveAnswer";
import { McqOptions } from "@/components/assessment/McqOptions";
import { QuestionCard } from "@/components/assessment/QuestionCard";
import { ResultSummary } from "@/components/assessment/ResultSummary";
import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { useAssessment, useSaveAnswer, useSubmitAssessment } from "@/hooks/useAssessment";

export default function AssessmentPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const assessmentId = Number(id);

  const { data: assessment, isPending } = useAssessment(assessmentId);
  const saveAnswer = useSaveAnswer(assessmentId);
  const submitAssessment = useSubmitAssessment(assessmentId);

  const [index, setIndex] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  if (isPending || !assessment) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  if (assessment.status === "completed") {
    return (
      <AppShell>
        <TopBar title="Assessment results" subtitle={`${assessment.level} level`} />
        <ResultSummary assessment={assessment} onContinue={() => navigate("/roadmap")} />
      </AppShell>
    );
  }

  const question = assessment.questions[index];
  const draft = drafts[question.id] ?? question.user_answer ?? "";
  const isLast = index === assessment.questions.length - 1;

  const setDraft = (value: string) => {
    setDrafts((prev) => ({ ...prev, [question.id]: value }));
  };

  const flush = (value: string) => {
    if (!value) return;
    saveAnswer.mutate({ questionId: question.id, answer: value });
  };

  const goNext = () => {
    flush(draft);
    setIndex((i) => Math.min(i + 1, assessment.questions.length - 1));
  };

  const goPrev = () => {
    flush(draft);
    setIndex((i) => Math.max(i - 1, 0));
  };

  const handleSubmit = async () => {
    flush(draft);
    await submitAssessment.mutateAsync();
    // No navigation needed: submitAssessment's onSuccess writes the
    // completed assessment into this same query's cache, so this component
    // re-renders straight into the status === "completed" branch above.
  };

  return (
    <AppShell>
      <TopBar
        title="Skill assessment"
        subtitle={`${assessment.level} level — answer honestly, this shapes your roadmap.`}
      />

      <div className="mb-6 h-1.5 w-full rounded-full bg-line">
        <div
          className="h-full rounded-full bg-accent transition-all duration-base"
          style={{ width: `${((index + 1) / assessment.questions.length) * 100}%` }}
        />
      </div>

      <QuestionCard question={question} index={index} total={assessment.questions.length}>
        {question.type === "mcq" && question.options ? (
          <McqOptions
            options={question.options}
            selected={draft === "" ? null : Number(draft)}
            onSelect={(optionIndex) => {
              const value = String(optionIndex);
              setDraft(value);
              flush(value);
            }}
          />
        ) : (
          <DescriptiveAnswer value={draft} onChange={setDraft} onBlur={() => flush(draft)} />
        )}
      </QuestionCard>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="secondary" onClick={goPrev} disabled={index === 0}>
          Previous
        </Button>
        {isLast ? (
          <Button onClick={handleSubmit} disabled={submitAssessment.isPending}>
            {submitAssessment.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Grading…
              </>
            ) : (
              "Submit assessment"
            )}
          </Button>
        ) : (
          <Button onClick={goNext}>Next</Button>
        )}
      </div>
    </AppShell>
  );
}
