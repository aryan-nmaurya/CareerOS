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
