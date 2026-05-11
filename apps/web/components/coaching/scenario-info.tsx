"use client";

import { useEffect, useState } from "react";
import { Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { fetchScenario } from "@/lib/api";
import { formatLabel } from "@/lib/utils";
import type { ScenarioDetail } from "@/lib/types";

interface ScenarioInfoProps {
  scenarioId: string;
}

export default function ScenarioInfo({ scenarioId }: ScenarioInfoProps) {
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchScenario(scenarioId)
      .then(setDetail)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [scenarioId]);

  if (loading) {
    return (
      <div className="mx-4 mt-2 rounded-lg border bg-secondary/30 p-4">
        <div className="flex items-center justify-center py-4">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        </div>
      </div>
    );
  }

  if (!detail) return null;

  return (
    <div className="mx-4 mt-2 rounded-lg border bg-secondary/30 p-4">
      <div className="flex items-start gap-2">
        <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div>
          <h3 className="text-sm font-medium">About this scenario</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {detail.setting}
          </p>
          {detail.skills_primary.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {detail.skills_primary.map((skill) => (
                <Badge key={skill} variant="outline" className="text-xs">
                  {formatLabel(skill)}
                </Badge>
              ))}
            </div>
          )}
          {detail.tags?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {detail.tags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="text-[10px]"
                >
                  {formatLabel(tag)}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
