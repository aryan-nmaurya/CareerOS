import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { LevelStep } from "@/components/onboarding/LevelStep";
import { NameStep } from "@/components/onboarding/NameStep";
import { TopicStep } from "@/components/onboarding/TopicStep";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useStartAssessment } from "@/hooks/useAssessment";
import { useCreateProfile, useCreateTrack, useProfile, useUpdateProfile } from "@/hooks/useProfile";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: profile } = useProfile();
  const createProfile = useCreateProfile();
  const updateProfile = useUpdateProfile();
  const createTrack = useCreateTrack();
  const startAssessment = useStartAssessment();

  const replay = new URLSearchParams(location.search).get("replay") === "1";
  // A replay starts from the name step; normal visits with an existing profile
  // start at topic selection so users can quickly add another track.
  const [step, setStep] = useState(replay ? 0 : profile ? 1 : 0);
  const [topic, setTopic] = useState("");

  useEffect(() => {
    if (!replay && profile && step === 0) setStep(1);
  }, [profile, replay, step]);

  const handleName = async (name: string) => {
    if (profile) await updateProfile.mutateAsync({ name });
    else await createProfile.mutateAsync(name);
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
        navigate("/roadmap", { replace: true });
        return;
      }
      const assessment = await startAssessment.mutateAsync(track.id);
      navigate(`/assessment/${assessment.id}`, { replace: true });
    } catch {
      // Surfaced via createTrack.error / startAssessment.error below —
      // nothing further to do here.
    }
  };

  const pending = createProfile.isPending || updateProfile.isPending || createTrack.isPending || startAssessment.isPending;
  const pendingLabel = startAssessment.isPending
    ? "Generating your assessment — this can take up to 30 seconds…"
    : "Setting up your track…";
  const errorMessage =
    updateProfile.error?.message ??
    createProfile.error?.message ??
    createTrack.error?.message ??
    startAssessment.error?.message;

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
