"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { AlertPayload } from "@/lib/types";

export function useAlertListener(userId: string | undefined) {
  const [pendingAlerts, setPendingAlerts] = useState<AlertPayload[]>([]);
  const [activeAlert, setActiveAlert] = useState<AlertPayload | null>(null);

  useEffect(() => {
    if (!userId) return;
    const supabase = createClient();
    const channel = supabase.channel(`user:${userId}`, {
      config: { broadcast: { self: false } },
    });

    channel.on("broadcast", { event: "alert" }, ({ payload }) => {
      setPendingAlerts((prev) => [...prev, payload as AlertPayload]);
    });

    channel.subscribe();
    return () => { channel.unsubscribe(); };
  }, [userId]);

  const consumeNextAlert = useCallback(() => {
    setPendingAlerts((prev) => {
      if (prev.length === 0) {
        setActiveAlert(null);
        return prev;
      }
      const [next, ...rest] = prev;
      setActiveAlert(next);
      return rest;
    });
  }, []);

  const dismissAlert = useCallback(() => {
    setActiveAlert(null);
  }, []);

  return {
    activeAlert,
    queueLength: pendingAlerts.length,
    consumeNextAlert,
    dismissAlert,
  };
}
