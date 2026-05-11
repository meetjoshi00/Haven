"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import AlertCard from "./AlertCard";
import type { AlertPayload } from "@/lib/types";

const MAX_ALERTS = 50;

interface AlertFeedPanelProps {
  alertList: AlertPayload[];
  userId: string;
}

export default function AlertFeedPanel({ alertList, userId }: AlertFeedPanelProps) {
  const [realtimeAlerts, setRealtimeAlerts] = useState<AlertPayload[]>([]);

  useEffect(() => {
    if (!userId) return;
    const supabase = createClient();
    const channel = supabase.channel(`user:${userId}`, {
      config: { broadcast: { self: false } },
    });

    channel.on("broadcast", { event: "alert" }, ({ payload }) => {
      setRealtimeAlerts((prev) =>
        [payload as AlertPayload, ...prev].slice(0, MAX_ALERTS)
      );
    });

    channel.subscribe();

    return () => {
      channel.unsubscribe();
    };
  }, [userId]);

  // Merge: realtime alerts first, then SSE-sourced alertList, deduplicated by alert_id
  const seen = new Set<string>();
  const merged: AlertPayload[] = [];
  for (const a of [...realtimeAlerts, ...alertList]) {
    if (!seen.has(a.alert_id)) {
      seen.add(a.alert_id);
      merged.push(a);
    }
    if (merged.length >= MAX_ALERTS) break;
  }

  if (merged.length === 0) {
    return (
      <div className="flex h-full flex-col">
        <p className="mb-3 text-sm font-medium">Alerts</p>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-muted-foreground">No alerts yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-medium">Alerts ({merged.length})</p>
      {merged.map((alert) => (
        <AlertCard key={alert.alert_id} alert={alert} />
      ))}
    </div>
  );
}
