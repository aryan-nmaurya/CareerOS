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
} | {
  type: "LOCAL_FATAL";
  eventType: ProctoringEventType;
};

export function warningsReducer(state: WarningsState, action: WarningsAction): WarningsState {
  if (state.terminated) return state;
  if (action.type === "LOCAL_FATAL") {
    return { ...state, terminated: true, recentEventType: action.eventType };
  }
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
      // Multiple faces are fatal by policy. Fail closed locally so the
      // interview cannot continue while the server event is in flight.
      if (eventType === "multiple_faces") {
        dispatch({ type: "LOCAL_FATAL", eventType });
      }
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
