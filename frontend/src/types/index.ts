export type ExperienceLevel = "beginner" | "intermediate" | "advanced";
export type Theme = "light" | "dark" | "system";

export interface Profile {
  id: number;
  name: string;
  theme: Theme;
  created_at: string;
}

export interface Track {
  id: number;
  topic: string;
  experience_level: ExperienceLevel;
  is_active: boolean;
  created_at: string;
}

export type QuestionType = "mcq" | "descriptive";
export type AssessmentStatus = "in_progress" | "completed";
export type EstimatedLevel = "foundational" | "intermediate" | "advanced";

export interface AssessmentQuestion {
  id: number;
  order_index: number;
  type: QuestionType;
  topic_tag: string;
  question: string;
  options: string[] | null;
  correct_option: number | null;
  expected_points: string[] | null;
  user_answer: string | null;
  score: number | null;
  ai_feedback: string | null;
}

export interface Assessment {
  id: number;
  track_id: number;
  level: ExperienceLevel;
  status: AssessmentStatus;
  started_at: string;
  completed_at: string | null;
  score: number | null;
  estimated_level: EstimatedLevel | null;
  strengths: string[];
  weaknesses: string[];
  summary: string | null;
  questions: AssessmentQuestion[];
}

export type ModuleKind = "module" | "checkpoint" | "milestone" | "project";

export interface RoadmapModule {
  id: number;
  order_index: number;
  title: string;
  description: string;
  lessons: string[];
  exercises: string[];
  project: { title: string; description: string } | null;
  estimated_hours: number;
  kind: ModuleKind;
  started_at: string | null;
  completed_at: string | null;
}

export interface RoadmapPhase {
  id: number;
  order_index: number;
  title: string;
  description: string;
  goal: string;
  estimated_hours: number;
  modules: RoadmapModule[];
}

export interface WeeklyGoal {
  week: number;
  goal: string;
  phase_order: number;
}

export interface FinalProject {
  title: string;
  description: string;
  skills_demonstrated: string[];
}

export interface PhaseProgress {
  order_index: number;
  completion_pct: number;
  unlocked: boolean;
}

export interface Progress {
  completion_pct: number;
  completed_modules: number;
  total_modules: number;
  current_phase_index: number;
  current_phase_title: string | null;
  phases: PhaseProgress[];
}

export interface Roadmap {
  id: number;
  track_id: number;
  title: string;
  summary: string;
  total_weeks: number;
  weekly_hours: number;
  weekly_goals: WeeklyGoal[];
  final_project: FinalProject | null;
  created_at: string;
  phases: RoadmapPhase[];
  progress: Progress;
}

export interface NextModule {
  id: number;
  title: string;
  kind: ModuleKind;
  phase_title: string;
}

export type InterviewLevel = "beginner" | "intermediate" | "advanced";
export type InterviewStatus = "setup" | "active" | "completed" | "terminated";

export interface InterviewQuestion {
  id: number;
  order_index: number;
  question: string;
  expected_points: string[];
  transcript: string | null;
  answer_duration_s: number | null;
}

export interface Interview {
  id: number;
  track_id: number;
  level: InterviewLevel;
  question_count: number;
  status: InterviewStatus;
  started_at: string;
  ended_at: string | null;
  termination_reason: string | null;
  questions: InterviewQuestion[];
}

export interface RecentInterview {
  id: number;
  level: InterviewLevel;
  status: InterviewStatus;
  started_at: string;
}

export interface Dashboard {
  profile: Profile | null;
  active_track: Track | null;
  roadmap_summary: string | null;
  current_phase: string | null;
  completed_modules: number;
  remaining_modules: number;
  completion_pct: number;
  next_module: NextModule | null;
  recent_interviews: RecentInterview[];
}

// Streamed phase/module data has no id yet — it isn't persisted-and-fetched
// until generation finishes; only the real GET /roadmap response (above) has
// ids. This is why RoadmapPage switches from the stream view to a real
// useRoadmap() query once the "done" event arrives, rather than trying to
// make the streamed data itself interactive.
export interface StreamModule {
  title: string;
  description: string;
  lessons: string[];
  exercises: string[];
  project: { title: string; description: string } | null;
  estimated_hours: number;
  kind: ModuleKind;
}

export interface StreamPhase {
  order_index: number;
  title: string;
  modules: StreamModule[];
}

export interface RoadmapMeta {
  title: string;
  summary: string;
  total_weeks: number;
  weekly_hours: number;
  weekly_goals: WeeklyGoal[];
  final_project: FinalProject | null;
}

export type MachinePhase = "briefing" | "speaking" | "answering" | "review";
