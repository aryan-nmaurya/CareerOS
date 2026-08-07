export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Thin fetch wrapper. Normalizes the backend's {detail: {code, message}} shape
 * into ApiError so callers can branch on `code` rather than parsing strings,
 * and maps 204 to null (the "not onboarded yet" signal from GET /api/profile).
 */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (response.status === 204) return null as T;

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = body?.detail;
    const isStructured = detail !== null && typeof detail === "object";
    throw new ApiError(
      response.status,
      isStructured && typeof detail.code === "string" ? detail.code : "unknown_error",
      isStructured && typeof detail.message === "string"
        ? detail.message
        : response.statusText,
    );
  }

  return body as T;
}
