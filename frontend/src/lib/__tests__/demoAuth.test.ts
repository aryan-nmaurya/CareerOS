import { beforeEach, describe, expect, it } from "vitest";

import { isSignedIn, signIn, signOut } from "@/lib/demoAuth";

describe("demoAuth", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("is not signed in before signIn is called", () => {
    expect(isSignedIn()).toBe(false);
  });

  it("is signed in after signIn", () => {
    signIn();
    expect(isSignedIn()).toBe(true);
  });

  it("is not signed in after signOut", () => {
    signIn();
    signOut();
    expect(isSignedIn()).toBe(false);
  });
});
