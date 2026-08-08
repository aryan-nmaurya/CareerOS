// Local dev sets VITE_API_BASE_URL explicitly (frontend/.env) to reach the
// standalone Uvicorn server on a different origin. Unset — as in production,
// where frontend and backend are one Vercel "services" deployment on a
// single origin — this defaults to "", making every call a same-origin
// relative request (e.g. "/api/profile") that Vercel's own rewrite routes
// to the backend service. It must never fall back to a hardcoded localhost
// URL: that would silently point a real deployment at the visitor's own
// machine instead of erroring.
export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

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
