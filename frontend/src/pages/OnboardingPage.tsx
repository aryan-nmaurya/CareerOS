import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { LevelStep } from "@/components/onboarding/LevelStep";
import { NameStep } from "@/components/onboarding/NameStep";
import { TopicStep } from "@/components/onboarding/TopicStep";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useStartAssessment } from "@/hooks/useAssessment";
import { useCreateProfile, useCreateTrack, useProfile } from "@/hooks/useProfile";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { data: profile } = useProfile();
  const createProfile = useCreateProfile();
  const createTrack = useCreateTrack();
  const startAssessment = useStartAssessment();

  // If a profile already exists we are here to add a track, not to re-onboard.
  const [step, setStep] = useState(profile ? 1 : 0);
  const [topic, setTopic] = useState("");

  const handleName = async (name: string) => {
    await createProfile.mutateAsync(name);
    setStep(1);
  };

  const handleTopic = (chosen: string) => {
    setTopic(chosen);
    setStep(2);
  };

  const handleLevel = async (level: ExperienceLevel) => {
    try {
      const track = await createTrack.mutateAsync({ topic, experienceLevel: level });
      if (level === "beginner") {
        navigate("/", { replace: true });
        return;
      }
      const assessment = await startAssessment.mutateAsync(track.id);
      navigate(`/assessment/${assessment.id}`, { replace: true });
    } catch {
      // Surfaced via createTrack.error / startAssessment.error below —
      // nothing further to do here.
    }
  };

  const pending = createTrack.isPending || startAssessment.isPending;
  const pendingLabel = startAssessment.isPending
    ? "Generating your assessment — this can take up to 30 seconds…"
    : "Setting up your track…";
  const errorMessage = createTrack.error?.message ?? startAssessment.error?.message;

  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-10 px-5 py-16">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">
            Career<span className="text-accent">OS</span>
          </span>
          <ThemeToggle />
        </div>

        <div className="flex gap-1.5" aria-hidden>
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-base",
                index <= step ? "bg-accent" : "bg-line",
              )}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.2 }}
          >
            {step === 0 && <NameStep onNext={handleName} />}
            {step === 1 && <TopicStep onNext={handleTopic} />}
            {step === 2 && (
              <LevelStep
                topic={topic}
                pending={pending}
                pendingLabel={pendingLabel}
                errorMessage={errorMessage}
                onSelect={handleLevel}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
