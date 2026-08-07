import { describe, expect, it } from "vitest";

import { resolveTheme } from "@/hooks/useTheme";

describe("resolveTheme", () => {
  it("returns the explicit choice regardless of system preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("follows the system preference when set to system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
});
