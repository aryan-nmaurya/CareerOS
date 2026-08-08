import { api } from "@/services/api/client";
import type { Interview, InterviewLevel, ProctoringEventType } from "@/types";

export const startInterview = (trackId: number, level: InterviewLevel, questionCount: number) =>
  api<Interview>(`/api/tracks/${trackId}/interviews`, {
    method: "POST",
    body: JSON.stringify({ level, question_count: questionCount }),
  });

export const getInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}`);

export const saveInterviewAnswer = (
  interviewId: number,
  questionId: number,
  transcript: string,
  durationS: number,
) =>
  api<null>(`/api/interviews/${interviewId}/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ transcript, duration_s: durationS }),
  });

export const submitInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}/submit`, { method: "POST" });

export const quitInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}/quit`, { method: "POST" });

export const recordEvent = (interviewId: number, type: ProctoringEventType, detail: string) =>
  api<{ warning_count: number; should_terminate: boolean }>(
    `/api/interviews/${interviewId}/events`,
    { method: "POST", body: JSON.stringify({ type, detail }) },
  );

export const listInterviews = () => api<Interview[]>("/api/interviews");
