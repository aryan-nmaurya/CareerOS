import { api } from "@/services/api/client";
import type { Assessment } from "@/types";

export const startAssessment = (trackId: number) =>
  api<Assessment>(`/api/tracks/${trackId}/assessment`, { method: "POST" });

export const getAssessment = (assessmentId: number) =>
  api<Assessment>(`/api/assessments/${assessmentId}`);

export const listAssessments = () => api<Assessment[]>("/api/assessments");

export const saveAnswer = (assessmentId: number, questionId: number, answer: string) =>
  api<null>(`/api/assessments/${assessmentId}/answers`, {
    method: "PATCH",
    body: JSON.stringify({ question_id: questionId, answer }),
  });

export const submitAssessment = (assessmentId: number) =>
  api<Assessment>(`/api/assessments/${assessmentId}/submit`, { method: "POST" });
