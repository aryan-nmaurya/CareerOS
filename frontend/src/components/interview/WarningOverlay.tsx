import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

const LABELS: Record<string, string> = {
  looking_away: "Looking away from the camera",
  no_face: "No face detected",
  multiple_faces: "Multiple faces detected",
  excessive_noise: "Excessive background noise",
  background_voice: "Background voice detected",
};

export function WarningOverlay({ warningCount, recentEventType }: { warningCount: number; recentEventType: string | null }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!warningCount) return;
    setVisible(true);
    const timer = window.setTimeout(() => setVisible(false), 4000);
    return () => window.clearTimeout(timer);
  }, [warningCount]);
  return <AnimatePresence>
    {visible && <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0, x: [0, -5, 5, -3, 3, 0] }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }} className="fixed left-1/2 top-5 z-50 -translate-x-1/2 rounded-lg border border-warning bg-surface px-4 py-3 shadow-lg">
      <div className="flex items-center gap-2 text-sm font-semibold"><AlertTriangle className="size-4 text-warning" />{warningCount >= 3 ? "Final warning" : `Warning ${warningCount} of 3`}</div>
      {recentEventType && <p className="mt-1 text-xs text-text-secondary">{LABELS[recentEventType] ?? recentEventType}</p>}
    </motion.div>}
  </AnimatePresence>;
}
