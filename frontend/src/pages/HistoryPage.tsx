import { ClipboardCheck, MessageSquare, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useAssessments } from "@/hooks/useAssessment";
import { useInterviews } from "@/hooks/useInterview";

export default function HistoryPage() {
  const assessments = useAssessments();
  const interviews = useInterviews();
  const loading = assessments.isPending || interviews.isPending;
  const error = assessments.error ?? interviews.error;
  const retry = () => { void assessments.refetch(); void interviews.refetch(); };
  return <AppShell><TopBar title="History" subtitle="Review your assessments and interview attempts." />{loading ? <LoadingState label="Loading history…" /> : error ? <ErrorState message={error instanceof Error ? error.message : "History unavailable."} onRetry={retry} /> : <div className="grid gap-6 md:grid-cols-2"><section className="space-y-3"><CardTitle>Assessments</CardTitle>{assessments.data?.length ? assessments.data.map((item) => <Card key={item.id} className="flex items-center justify-between gap-3"><div className="flex items-center gap-3"><ClipboardCheck className="size-5 text-accent" /><div><p className="font-medium">{item.level} assessment</p><CardDescription>{new Date(item.started_at).toLocaleDateString()} · {item.status === "completed" ? `${Math.round(item.score ?? 0)} / 100` : "In progress"}</CardDescription></div></div><Link to={`/assessment/${item.id}`} className="text-accent"><ArrowRight className="size-4" /></Link></Card>) : <CardDescription>No assessments yet.</CardDescription>}</section><section className="space-y-3"><CardTitle>Interviews</CardTitle>{interviews.data?.length ? interviews.data.map((item) => <Card key={item.id} className="flex items-center justify-between gap-3"><div className="flex items-center gap-3"><MessageSquare className="size-5 text-accent" /><div><p className="font-medium">{item.level} mock interview</p><CardDescription>{new Date(item.started_at).toLocaleDateString()} · {item.status}</CardDescription></div></div><Link to={`/interview/${item.id}/report`} className="text-accent"><ArrowRight className="size-4" /></Link></Card>) : <CardDescription>No interviews yet.</CardDescription>}</section></div>}</AppShell>;
}
