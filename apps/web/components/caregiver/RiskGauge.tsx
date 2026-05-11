"use client";

import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";

interface RiskGaugeProps {
  riskScore: number;
  severity: string | null;
  causeTags: string[];
  modelType: "full" | "wearable";
  isDemo: boolean;
}

function getRiskLevel(score: number): { label: string; color: string } {
  if (score < 0.35) return { label: "Low", color: "#5a7d4e" };
  if (score < 0.65) return { label: "Moderate", color: "#c17f24" };
  return { label: "Elevated", color: "#b84f28" };
}

export default function RiskGauge({
  riskScore,
  causeTags,
  modelType,
  isDemo,
}: RiskGaugeProps) {
  const arcRef = useRef<SVGPathElement>(null);
  const prefersReducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  const { label, color } = getRiskLevel(riskScore);

  // pathLength="1" lets strokeDashoffset map directly to 0-1 fraction of arc
  const offset = 1 - Math.max(0, Math.min(1, riskScore));

  useEffect(() => {
    const el = arcRef.current;
    if (!el) return;
    if (prefersReducedMotion) {
      el.style.transition = "none";
    } else {
      el.style.transition = "stroke-dashoffset 0.6s ease, stroke 0.4s ease";
    }
  }, [prefersReducedMotion]);

  const auroc =
    modelType === "full"
      ? "AUROC 0.88"
      : "AUROC 0.62 — lower confidence";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative">
        <svg
          viewBox="0 0 200 110"
          width={200}
          height={110}
          aria-label={`Stress escalation risk: ${label}`}
          role="img"
        >
          {/* Background arc track */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth={14}
            strokeLinecap="round"
          />
          {/* Filled arc — pathLength trick */}
          <path
            ref={arcRef}
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={color}
            strokeWidth={14}
            strokeLinecap="round"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset={offset}
          />
          {/* Center label */}
          <text
            x="100"
            y="88"
            textAnchor="middle"
            fontSize="16"
            fontWeight="600"
            fill="hsl(var(--foreground))"
          >
            {label}
          </text>
          {isDemo && (
            <text
              x="100"
              y="104"
              textAnchor="middle"
              fontSize="9"
              fill="hsl(var(--muted-foreground))"
            >
              Demo
            </text>
          )}
        </svg>
      </div>

      {/* Cause tag chips */}
      {causeTags.length > 0 && (
        <div className="flex flex-wrap justify-center gap-1.5">
          {causeTags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag.replace(/_/g, " ")}
            </Badge>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">{auroc}</p>
    </div>
  );
}
