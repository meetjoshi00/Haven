"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  acknowledgeAlert,
  fetchAlertDetail,
  fetchAlerts,
  reportFalseAlarm,
} from "@/lib/api";
import type { AlertDetail, AlertListItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

function relativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const SEVERITY_OPTIONS = [
  { value: "", label: "All" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
] as const;

const STATUS_OPTIONS = [
  { key: "all", label: "All" },
  { key: "false_alarm", label: "False Alarm" },
  { key: "acknowledged", label: "Acknowledged" },
] as const;

export default function AlertsPage() {
  const [userId, setUserId] = useState<string | null>(null);
  const [items, setItems] = useState<AlertListItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const [severityFilter, setSeverityFilter] = useState("");
  const [falseAlarmOnly, setFalseAlarmOnly] = useState(false);
  const [ackedOnly, setAckedOnly] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [faInputId, setFaInputId] = useState<string | null>(null);
  const [faNotes, setFaNotes] = useState("");

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setUserId(data.user?.id ?? null);
    });
  }, []);

  async function load(reset = false) {
    if (!userId) return;
    const newOffset = reset ? 0 : offset;
    setLoading(true);
    try {
      const data = await fetchAlerts(userId, {
        limit: PAGE_SIZE,
        offset: newOffset,
        severity: severityFilter || undefined,
      });
      const filtered = falseAlarmOnly
        ? data.filter((a) => a.false_alarm)
        : ackedOnly
        ? data.filter((a) => a.acknowledged)
        : data;
      if (reset) {
        setItems(filtered);
        setOffset(PAGE_SIZE);
      } else {
        setItems((prev) => [...prev, ...filtered]);
        setOffset(newOffset + PAGE_SIZE);
      }
      setHasMore(data.length === PAGE_SIZE);
    } finally {
      setLoading(false);
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (userId) load(true); }, [userId, severityFilter, falseAlarmOnly, ackedOnly]);

  async function toggleExpand(alertId: string) {
    if (expandedId === alertId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(alertId);
    setDetail(null);
    setDetailLoading(true);
    try {
      const d = await fetchAlertDetail(alertId);
      setDetail(d);
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleAcknowledge(alertId: string) {
    setActionLoading(alertId + ":ack");
    try {
      await acknowledgeAlert(alertId, "caregiver");
      setItems((prev) =>
        prev.map((a) => (a.alert_id === alertId ? { ...a, acknowledged: true } : a))
      );
    } finally {
      setActionLoading(null);
    }
  }

  async function handleFalseAlarm(alertId: string) {
    setActionLoading(alertId + ":fa");
    try {
      await reportFalseAlarm(alertId, "caregiver", faNotes || undefined);
      setItems((prev) =>
        prev.map((a) => (a.alert_id === alertId ? { ...a, false_alarm: true } : a))
      );
      setFaInputId(null);
      setFaNotes("");
    } finally {
      setActionLoading(null);
    }
  }

  const severityBadge = (s: string) =>
    s === "high"
      ? "bg-orange-100 text-orange-900 border-orange-200"
      : "bg-amber-100 text-amber-900 border-amber-200";

  const activeStatus = falseAlarmOnly ? "false_alarm" : ackedOnly ? "acknowledged" : "all";

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Alert History</h1>
      </div>

      {/* Filters — pill groups */}
      <div className="flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Severity</span>
          <div className="flex gap-1.5">
            {SEVERITY_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setSeverityFilter(value)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  severityFilter === value
                    ? "bg-[#282079] text-white"
                    : "bg-muted text-muted-foreground hover:bg-accent"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Status</span>
          <div className="flex gap-1.5">
            {STATUS_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => {
                  setFalseAlarmOnly(key === "false_alarm");
                  setAckedOnly(key === "acknowledged");
                }}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  activeStatus === key
                    ? "bg-[#282079] text-white"
                    : "bg-muted text-muted-foreground hover:bg-accent"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alert rows */}
      <div className="flex flex-col gap-2">
        {items.length === 0 && !loading && (
          <p className="text-sm text-muted-foreground">No alerts found.</p>
        )}

        {items.map((item) => (
          <div key={item.alert_id} className="rounded-lg border bg-card">
            <button
              className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-accent/40 transition-colors rounded-lg"
              onClick={() => toggleExpand(item.alert_id)}
            >
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs font-medium capitalize shrink-0",
                  severityBadge(item.severity)
                )}
              >
                {item.severity}
              </span>
              <span className="flex-1 text-sm font-medium truncate">{item.headline}</span>
              <div className="flex items-center gap-2 shrink-0">
                {item.acknowledged && (
                  <Badge variant="outline" className="text-xs">Acknowledged</Badge>
                )}
                {item.false_alarm && (
                  <Badge variant="outline" className="text-xs text-muted-foreground">
                    False Alarm
                  </Badge>
                )}
                {item.demo && (
                  <Badge variant="secondary" className="text-xs">Demo</Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {relativeTime(item.ts)}
                </span>
              </div>
            </button>

            {expandedId === item.alert_id && (
              <div className="border-t px-4 py-3 space-y-3 text-sm">
                {detailLoading ? (
                  <p className="text-xs text-muted-foreground">Loading…</p>
                ) : detail ? (
                  <>
                    {detail.why && (
                      <p className="italic text-xs text-muted-foreground">{detail.why}</p>
                    )}
                    <p>{detail.caregiver_message}</p>
                    {detail.recommended_actions.length > 0 && (
                      <ul className="list-disc list-inside space-y-0.5 text-xs text-muted-foreground">
                        {detail.recommended_actions.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    )}
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-muted-foreground border-t pt-3">
                      {Object.entries(detail.features)
                        .filter(([, v]) => v !== 0)
                        .slice(0, 8)
                        .map(([k, v]) => (
                          <span key={k}>
                            <span className="font-medium text-foreground">{k.replace(/_/g, " ")}</span>{" "}
                            {typeof v === "number" ? v.toFixed(3) : v}
                          </span>
                        ))}
                    </div>
                    {!item.acknowledged && !item.false_alarm && (
                      <div className="flex flex-col gap-2">
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleAcknowledge(item.alert_id)}
                            disabled={actionLoading !== null}
                          >
                            {actionLoading === item.alert_id + ":ack" ? "…" : "Acknowledged"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setFaInputId((prev) =>
                                prev === item.alert_id ? null : item.alert_id
                              )
                            }
                            disabled={actionLoading !== null}
                          >
                            False alarm
                          </Button>
                        </div>
                        {faInputId === item.alert_id && (
                          <div className="flex flex-col gap-2">
                            <textarea
                              value={faNotes}
                              onChange={(e) => setFaNotes(e.target.value)}
                              placeholder="Optional notes…"
                              rows={2}
                              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-ring"
                            />
                            <Button
                              size="sm"
                              onClick={() => handleFalseAlarm(item.alert_id)}
                              disabled={actionLoading !== null}
                            >
                              {actionLoading === item.alert_id + ":fa" ? "…" : "Submit"}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : null}
              </div>
            )}
          </div>
        ))}
      </div>

      {hasMore && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => load()}
          disabled={loading}
          className="self-start"
        >
          {loading ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  );
}
