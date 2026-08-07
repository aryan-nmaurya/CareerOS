import type { ExperienceLevel } from "@/types";

export const PRESET_TOPICS = [
  "Python",
  "JavaScript",
  "TypeScript",
  "Git & GitHub",
  "React",
  "Node.js",
  "Express.js",
  "Full Stack Development",
  "Software Development",
  "AI",
  "Machine Learning",
  "Deep Learning",
  "MLOps",
  "DevOps",
  "SQL",
  "PostgreSQL",
  "Docker",
  "Kubernetes",
  "Cloud Computing",
  "Data Structures & Algorithms",
] as const;

export const EXPERIENCE_LEVELS: {
  value: ExperienceLevel;
  label: string;
  description: string;
}[] = [
  {
    value: "beginner",
    label: "Beginner",
    description:
      "New to this. We skip the assessment and build a roadmap from the fundamentals up.",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    description:
      "You know some of it. A short assessment finds your gaps, then the roadmap targets them.",
  },
  {
    value: "advanced",
    label: "Advanced (Revision)",
    description:
      "You want to sharpen up. A harder assessment drives a roadmap of weak spots, advanced projects, and interview prep.",
  },
];
