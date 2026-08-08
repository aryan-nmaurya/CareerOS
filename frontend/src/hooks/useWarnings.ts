import { useCallback, useReducer } from "react";

import { useRecordEvent } from "@/hooks/useInterview";
import type { ProctoringEventType } from "@/types";

export interface WarningsState {
  warningCount: number;
  terminated: boolean;
  recentEventType: ProctoringEventType | null;
}

export function initialWarningsState(): WarningsState {
  return { warningCount: 0, terminated: false, recentEventType: null };
}

export type WarningsAction = {
  type: "SERVER_RESULT";
  eventType: ProctoringEventType;
  warningCount: number;
  shouldTerminate: boolean;
};

export function warningsReducer(state: WarningsState, action: WarningsAction): WarningsState {
  if (state.terminated) return state;
  return {
    warningCount: action.warningCount,
    terminated: action.shouldTerminate,
    recentEventType: action.eventType,
  };
}

export function useWarnings(interviewId: number) {
  const [state, dispatch] = useReducer(warningsReducer, initialWarningsState());
  const mutation = useRecordEvent(interviewId);

  const reportEvent = useCallback(
    (eventType: ProctoringEventType, detail: string) => {
      mutation.mutate(
        { type: eventType, detail },
        {
          onSuccess: (result) =>
            dispatch({
              type: "SERVER_RESULT",
              eventType,
              warningCount: result.warning_count,
              shouldTerminate: result.should_terminate,
            }),
        },
      );
    },
    [mutation],
  );

  return { ...state, reportEvent };
}
