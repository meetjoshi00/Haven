"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AlertPayload } from "@/lib/types";
import { acknowledgeAlert, reportFalseAlarm } from "@/lib/api";

interface AlertCardProps {
  alert: AlertPayload;
  onUpdate?: () => void;
}

function relativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function AlertCard({ alert, onUpdate }: AlertCardProps) {
  const [showCaregiver, setShowCaregiver] = useState(false);
  const [showFalseAlarmInput, setShowFalseAlarmInput] = useState(false);
  const [falseAlarmNotes, setFalseAlarmNotes] = useState("");
  const [loading, setLoading] = useState<"ack" | "fa" | null>(null);
  const [done, setDone] = useState<"ack" | "fa" | null>(null);

  async function handleAcknowledge() {
    setLoading("ack");
    try {
      await acknowledgeAlert(alert.alert_id, "caregiver");
      setDone("ack");
      onUpdate?.();
    } finally {
      setLoading(null);
    }
  }

  async function handleFalseAlarm() {
    setLoading("fa");
    try {
      await reportFalseAlarm(alert.alert_id, "caregiver", falseAlarmNotes || undefined);
      setDone("fa");
      setShowFalseAlarmInput(false);
      onUpdate?.();
    } finally {
      setLoading(null);
    }
  }

  const severityClass =
    alert.severity === "high"
      ? "bg-orange-100 text-orange-900 border-orange-200"
      : "bg-amber-100 text-amber-900 border-amber-200";

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold leading-snug">{alert.headline}</p>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
              severityClass
            )}
          >
            {alert.severity}
          </span>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {relativeTime(alert.ts)}
          </span>
        </div>
      </div>

      {alert.why && (
        <p className="italic text-muted-foreground text-xs">{alert.why}</p>
      )}

      <p className="text-sm">
        {showCaregiver ? alert.caregiver_message : alert.person_message}
      </p>

      <button
        onClick={() => setShowCaregiver((v) => !v)}
        className="text-xs text-primary underline-offset-4 hover:underline"
      >
        {showCaregiver ? "Show person view" : "Show caregiver view"}
      </button>

      {alert.recommended_actions.length > 0 && (
        <ul className="list-disc list-inside space-y-0.5 text-xs text-muted-foreground">
          {alert.recommended_actions.map((action, i) => (
            <li key={i}>{action}</li>
          ))}
        </ul>
      )}

      {done === "ack" ? (
        <p className="text-xs text-muted-foreground">Acknowledged</p>
      ) : done === "fa" ? (
        <p className="text-xs text-muted-foreground">Logged as false alarm</p>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleAcknowledge}
              disabled={loading !== null}
            >
              {loading === "ack" ? "..." : "Acknowledged"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowFalseAlarmInput((v) => !v)}
              disabled={loading !== null}
            >
              False alarm
            </Button>
          </div>

          {showFalseAlarmInput && (
            <div className="flex flex-col gap-2">
              <textarea
                value={falseAlarmNotes}
                onChange={(e) => setFalseAlarmNotes(e.target.value)}
                placeholder="Optional notes…"
                rows={2}
                className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <Button
                size="sm"
                onClick={handleFalseAlarm}
                disabled={loading !== null}
              >
                {loading === "fa" ? "..." : "Submit"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
