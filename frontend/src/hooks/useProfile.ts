import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProfile,
  createTrack,
  deleteProfile,
  getProfile,
  listTracks,
  updateProfile,
} from "@/services/api/profile";
import type { ExperienceLevel } from "@/types";

export const profileKey = ["profile"] as const;
export const tracksKey = ["tracks"] as const;

export function useProfile() {
  return useQuery({ queryKey: profileKey, queryFn: getProfile });
}

export function useTracks() {
  return useQuery({ queryKey: tracksKey, queryFn: listTracks });
}

export function useActiveTrack() {
  const { data, ...rest } = useTracks();
  return { data: data?.find((track) => track.is_active) ?? null, ...rest };
}

export function useCreateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => createProfile(name),
    onSuccess: (profile) => queryClient.setQueryData(profileKey, profile),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => queryClient.setQueryData(profileKey, profile),
  });
}

export function useCreateTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      topic,
      experienceLevel,
    }: {
      topic: string;
      experienceLevel: ExperienceLevel;
    }) => createTrack(topic, experienceLevel),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tracksKey }),
  });
}

export function useDeleteProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => queryClient.clear(),
  });
}
