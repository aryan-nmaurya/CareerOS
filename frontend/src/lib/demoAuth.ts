const SIGNED_IN_KEY = "careeros_signed_in";

export const DEMO_EMAIL = "demo@careeros.app";
export const DEMO_PASSWORD = "CareerOS#2026";

export function isSignedIn(): boolean {
  return localStorage.getItem(SIGNED_IN_KEY) === "true";
}

export function signIn(): void {
  localStorage.setItem(SIGNED_IN_KEY, "true");
}

export function signOut(): void {
  localStorage.removeItem(SIGNED_IN_KEY);
}
