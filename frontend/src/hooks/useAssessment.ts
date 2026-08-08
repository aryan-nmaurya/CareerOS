import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAssessment,
  listAssessments,
  saveAnswer,
  startAssessment,
  submitAssessment,
} from "@/services/api/assessment";

export const assessmentKey = (id: number) => ["assessment", id] as const;

export function useAssessment(assessmentId: number) {
  return useQuery({
    queryKey: assessmentKey(assessmentId),
    queryFn: () => getAssessment(assessmentId),
  });
}

export function useStartAssessment() {
  return useMutation({ mutationFn: (trackId: number) => startAssessment(trackId) });
}

export function useSaveAnswer(assessmentId: number) {
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: number; answer: string }) =>
      saveAnswer(assessmentId, questionId, answer),
  });
}

export function useSubmitAssessment(assessmentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitAssessment(assessmentId),
    onSuccess: (data) => queryClient.setQueryData(assessmentKey(assessmentId), data),
  });
}

export function useAssessments() {
  return useQuery({ queryKey: ["assessments"], queryFn: listAssessments });
}
