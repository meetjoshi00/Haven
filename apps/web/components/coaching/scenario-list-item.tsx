"use client";

import { Coffee, Ear, Briefcase, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Scenario } from "@/lib/types";

const DOMAIN_ICONS: Record<string, LucideIcon> = {
  social: Coffee,
  sensory: Ear,
  workplace: Briefcase,
};

const DOMAIN_BG: Record<string, string> = {
  social: "bg-domain-social-light text-domain-social",
  sensory: "bg-domain-sensory-light text-domain-sensory",
  workplace: "bg-domain-workplace-light text-domain-workplace",
};

function DifficultyDots({ level }: { level: number }) {
  return (
    <div className="flex gap-0.5" aria-label={`Difficulty ${level} of 3`}>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            i <= level ? "bg-foreground/60" : "bg-foreground/15"
          )}
        />
      ))}
    </div>
  );
}

interface ScenarioListItemProps {
  scenario: Scenario;
  loading?: boolean;
  onClick: () => void;
}

export default function ScenarioListItem({
  scenario,
  loading,
  onClick,
}: ScenarioListItemProps) {
  const Icon = DOMAIN_ICONS[scenario.domain] ?? Coffee;
  const bgClass = DOMAIN_BG[scenario.domain] ?? DOMAIN_BG.social;

  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2.5 text-left transition-colors hover:bg-accent disabled:opacity-50"
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          bgClass
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{scenario.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {scenario.persona_name || scenario.setting}
        </p>
      </div>

      <div className="shrink-0">
        {loading ? (
          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        ) : (
          <DifficultyDots level={scenario.difficulty} />
        )}
      </div>
    </button>
  );
}
