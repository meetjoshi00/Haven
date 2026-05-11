import { describe, it, expect } from "vitest";
import { DOMAIN_LABELS, DIFFICULTY_LABELS, DOMAIN_COLORS, APP_NAME } from "@/lib/constants";

describe("constants", () => {
  it("APP_NAME is set", () => {
    expect(APP_NAME).toBe("ASD Coach");
  });

  it("DOMAIN_LABELS covers all three domains", () => {
    expect(DOMAIN_LABELS.social).toBe("Social");
    expect(DOMAIN_LABELS.sensory).toBe("Sensory");
    expect(DOMAIN_LABELS.workplace).toBe("Workplace");
  });

  it("DIFFICULTY_LABELS covers levels 1-3", () => {
    expect(DIFFICULTY_LABELS[1]).toBe("Beginner");
    expect(DIFFICULTY_LABELS[2]).toBe("Intermediate");
    expect(DIFFICULTY_LABELS[3]).toBe("Advanced");
  });

  it("DOMAIN_COLORS has bg, text, and light for each domain", () => {
    for (const domain of ["social", "sensory", "workplace"]) {
      const c = DOMAIN_COLORS[domain];
      expect(c).toHaveProperty("bg");
      expect(c).toHaveProperty("text");
      expect(c).toHaveProperty("light");
    }
  });
});
