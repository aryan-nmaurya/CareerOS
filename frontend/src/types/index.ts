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
