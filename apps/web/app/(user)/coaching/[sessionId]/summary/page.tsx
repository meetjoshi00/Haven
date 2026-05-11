"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { endSession, startSession } from "@/lib/api";
import { useUser } from "@/hooks/use-user";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatLabel } from "@/lib/utils";
import type { SessionEndResponse } from "@/lib/types";

export default function SummaryPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { user } = useUser();
  const [summary, setSummary] = useState<SessionEndResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState(false);
  const [storedMeta, setStoredMeta] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(`session_${params.sessionId}`);
    if (stored) {
      try { setStoredMeta(JSON.parse(stored)); } catch {}
    }

    endSession(params.sessionId)
      .then((data) => {
        setSummary(data);
        sessionStorage.removeItem(`session_${params.sessionId}`);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [params.sessionId]);

  const scenarioId = storedMeta?.scenario_id as string | undefined;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-muted-foreground">
          Could not load session summary.
        </p>
        <Button variant="outline" onClick={() => router.push("/coaching")}>
          Back to scenarios
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm">
        <h1 className="text-lg font-semibold">Session Summary</h1>

        <div className="mt-6 flex items-baseline gap-2">
          <span className="text-4xl font-bold">{summary.avg_score.toFixed(1)}</span>
          <span className="text-sm text-muted-foreground">out of 5</span>
        </div>

        {summary.skills_practiced.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Skills practiced
            </p>
            <div className="flex flex-wrap gap-1.5">
              {summary.skills_practiced.map((skill) => (
                <Badge key={skill} variant="secondary">
                  {formatLabel(skill)}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
          {summary.summary}
        </p>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <Button
            className="flex-1"
            onClick={() => router.push("/coaching")}
          >
            Try another scenario
          </Button>
          {scenarioId && user && (
            <Button
              variant="outline"
              className="flex-1"
              disabled={restarting}
              onClick={async () => {
                setRestarting(true);
                try {
                  const res = await startSession(user.id, scenarioId);
                  sessionStorage.setItem(
                    `session_${res.session_id}`,
                    JSON.stringify({
                      ...storedMeta,
                      opening_line: res.opening_line,
                    }),
                  );
                  router.push(`/coaching/${res.session_id}`);
                } catch {
                  router.push("/coaching");
                } finally {
                  setRestarting(false);
                }
              }}
            >
              {restarting ? "Starting…" : "Practice again"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
