import { api } from "@/services/api/client";
import type { ExperienceLevel, Profile, Theme, Track } from "@/types";

export const getProfile = () => api<Profile | null>("/api/profile");

export const createProfile = (name: string) =>
  api<Profile>("/api/profile", { method: "POST", body: JSON.stringify({ name }) });

export const updateProfile = (payload: { name?: string; theme?: Theme }) =>
  api<Profile>("/api/profile", { method: "PATCH", body: JSON.stringify(payload) });

export const listTracks = () => api<Track[]>("/api/tracks");

export const createTrack = (topic: string, experienceLevel: ExperienceLevel) =>
  api<Track>("/api/tracks", {
    method: "POST",
    body: JSON.stringify({ topic, experience_level: experienceLevel }),
  });

export const deleteProfile = () => api<null>("/api/profile", { method: "DELETE" });
