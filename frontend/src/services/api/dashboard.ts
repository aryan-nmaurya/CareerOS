import { api } from "@/services/api/client";
import type { Dashboard } from "@/types";

export const getDashboard = () => api<Dashboard>("/api/dashboard");
