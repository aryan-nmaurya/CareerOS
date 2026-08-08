import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useInterview } from "@/hooks/useInterview";

function Score({ label, value }: { label: string; value: number | null }) {
  return <div className="rounded-lg border border-line p-4"><p className="text-xs text-text-muted">{label}</p><p className="mt-1 text-2xl font-semibold">{value === null ? "—" : Math.round(value)}</p></div>;
}

export default function InterviewReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: interview, isPending, error, refetch } = useInterview(Number(id));
  if (isPending) return <AppShell><LoadingState label="Loading report…" /></AppShell>;
  if (error || !interview) return <AppShell><ErrorState message={error instanceof Error ? error.message : "This interview could not be found."} onRetry={() => void refetch()} /></AppShell>;
  return <AppShell>
    <TopBar title="Interview Report" subtitle={`${interview.level.charAt(0).toUpperCase()}${interview.level.slice(1)} Interview · ${new Date(interview.started_at).toLocaleDateString()}`} />
    <div className="space-y-6">
      <Link to="/history" className="inline-flex items-center gap-2 text-sm text-accent"><ArrowLeft className="size-4" /> History</Link>
      {interview.status === "terminated" ? <Card><CardTitle>Interview terminated</CardTitle><CardDescription>This attempt was not scored because it ended before all answers were completed.</CardDescription></Card> : <>
        <section className="grid gap-3 sm:grid-cols-4"><Score label="Overall" value={interview.overall_score} /><Score label="Technical" value={interview.technical_score} /><Score label="Communication" value={interview.communication_score} /><Score label="Confidence" value={interview.confidence_score} /></section>
        {interview.summary && <Card><CardTitle>Summary</CardTitle><CardDescription className="mt-2">{interview.summary}</CardDescription></Card>}
        <section className="grid gap-4 md:grid-cols-3"><Card><CardTitle>Strengths</CardTitle><ul className="mt-3 space-y-2 text-sm">{interview.strengths.map((item) => <li key={item} className="flex gap-2"><CheckCircle2 className="mt-0.5 size-4 text-success" />{item}</li>)}</ul></Card><Card><CardTitle>Weaknesses</CardTitle><ul className="mt-3 space-y-2 text-sm">{interview.weaknesses.map((item) => <li key={item} className="flex gap-2"><XCircle className="mt-0.5 size-4 text-danger" />{item}</li>)}</ul></Card><Card><CardTitle>Recommendations</CardTitle><ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{interview.recommendations.map((item) => <li key={item}>{item}</li>)}</ul></Card></section>
        <section className="space-y-3"><CardTitle>Question breakdown</CardTitle>{interview.questions.map((question, index) => <Card key={question.id} className="space-y-3"><div className="flex items-start justify-between gap-4"><div><p className="text-xs text-text-muted">Question {index + 1}</p><CardTitle className="mt-1">{question.question}</CardTitle></div><span className="whitespace-nowrap text-sm font-semibold">{question.technical_score === null ? "—" : `${Math.round(question.technical_score * 10)} / 100`}</span></div>{question.feedback && <CardDescription>{question.feedback}</CardDescription>}{question.missing_concepts.length > 0 && <p className="text-sm"><span className="font-medium">Missing concepts:</span> {question.missing_concepts.join(", ")}</p>}{question.better_answer && <div className="rounded-lg bg-surface-hover p-3 text-sm"><p className="font-medium">Better answer</p><p className="mt-1 text-text-secondary">{question.better_answer}</p></div>}</Card>)}</section>
      </>}
    </div>
  </AppShell>;
}
