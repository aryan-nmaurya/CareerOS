import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardKey } from "@/hooks/useDashboard";
import {
  getInterview,
  quitInterview,
  saveInterviewAnswer,
  startInterview,
  submitInterview,
} from "@/services/api/interview";
import type { InterviewLevel } from "@/types";

export const interviewKey = (id: number) => ["interview", id] as const;

export function useInterview(interviewId: number) {
  return useQuery({
    queryKey: interviewKey(interviewId),
    queryFn: () => getInterview(interviewId),
  });
}

export function useStartInterview() {
  return useMutation({
    mutationFn: ({
      trackId,
      level,
      questionCount,
    }: {
      trackId: number;
      level: InterviewLevel;
      questionCount: number;
    }) => startInterview(trackId, level, questionCount),
  });
}

export function useSaveInterviewAnswer(interviewId: number) {
  return useMutation({
    mutationFn: ({
      questionId,
      transcript,
      durationS,
    }: {
      questionId: number;
      transcript: string;
      durationS: number;
    }) => saveInterviewAnswer(interviewId, questionId, transcript, durationS),
  });
}

export function useSubmitInterview(interviewId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitInterview(interviewId),
    onSuccess: (data) => {
      queryClient.setQueryData(interviewKey(interviewId), data);
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}

export function useQuitInterview(interviewId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quitInterview(interviewId),
    onSuccess: (data) => {
      queryClient.setQueryData(interviewKey(interviewId), data);
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}
