"use client";

import AnimatedOrb from "@/components/ui/animated-orb";

function getGreeting() {
  const h = new Date().getHours();
  if (h >= 22) return "Welcome back!";
  if (h < 12) return "Good morning!";
  if (h < 17) return "Good afternoon!";
  return "Good evening!";
}

export default function CoachingLanding() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4">
      <AnimatedOrb size={260} className="mb-8" />

      <p className="text-sm text-muted-foreground">{getGreeting()}</p>
      <h1 className="mt-1 text-xl font-semibold text-foreground">
        Choose a scenario to begin
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Select a practice scenario from the panel
      </p>

      <div className="mt-6 flex items-center gap-6 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <DifficultyDots count={1} /> Beginner
        </span>
        <span className="flex items-center gap-1.5">
          <DifficultyDots count={2} /> Intermediate
        </span>
        <span className="flex items-center gap-1.5">
          <DifficultyDots count={3} /> Advanced
        </span>
      </div>

    </div>
  );
}

function DifficultyDots({ count }: { count: number }) {
  return (
    <span className="flex gap-0.5">
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={`inline-block h-1.5 w-1.5 rounded-full ${
            i <= count ? "bg-foreground/60" : "bg-foreground/15"
          }`}
        />
      ))}
    </span>
  );
}
