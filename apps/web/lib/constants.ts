export const APP_NAME = "ASD Coach";

export const DOMAIN_LABELS: Record<string, string> = {
  social: "Social",
  sensory: "Sensory",
  workplace: "Workplace",
};

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Beginner",
  2: "Intermediate",
  3: "Advanced",
};

export const DOMAIN_COLORS: Record<
  string,
  { bg: string; text: string; light: string }
> = {
  social: {
    bg: "bg-domain-social",
    text: "text-domain-social",
    light: "bg-domain-social-light",
  },
  sensory: {
    bg: "bg-domain-sensory",
    text: "text-domain-sensory",
    light: "bg-domain-sensory-light",
  },
  workplace: {
    bg: "bg-domain-workplace",
    text: "text-domain-workplace",
    light: "bg-domain-workplace-light",
  },
};
