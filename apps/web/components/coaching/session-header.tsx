"use client";

import { Info, RotateCcw, Coffee, Ear, Briefcase, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { DOMAIN_LABELS, DIFFICULTY_LABELS } from "@/lib/constants";

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

interface SessionHeaderProps {
  title: string;
  domain: string;
  difficulty: number;
  turnNumber: number;
  turnsRemaining: number;
  showInfo: boolean;
  onToggleInfo: () => void;
  onRestart: () => void;
}

export default function SessionHeader({
  title,
  domain,
  difficulty,
  turnNumber,
  turnsRemaining,
  showInfo,
  onToggleInfo,
  onRestart,
}: SessionHeaderProps) {
  const Icon = DOMAIN_ICONS[domain] ?? Coffee;
  const bgClass = DOMAIN_BG[domain] ?? DOMAIN_BG.social;

  return (
    <div className="flex items-center gap-3 border-b px-4 py-3">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
          bgClass
        )}
      >
        <Icon className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold">{title}</h1>
        <div className="flex items-center gap-2 mt-0.5">
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {DOMAIN_LABELS[domain] ?? domain}
          </Badge>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {DIFFICULTY_LABELS[difficulty] ?? `Level ${difficulty}`}
          </Badge>
          <span className="text-[10px] text-muted-foreground">
            Turn {turnNumber} · {turnsRemaining} left
          </span>
        </div>
      </div>

      <button
        onClick={onToggleInfo}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
          showInfo
            ? "bg-accent text-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )}
        aria-label="Toggle scenario info"
      >
        <Info className="h-4 w-4" />
      </button>

      <button
        onClick={onRestart}
        className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label="Restart conversation"
      >
        <RotateCcw className="h-4 w-4" />
      </button>
    </div>
  );
}
