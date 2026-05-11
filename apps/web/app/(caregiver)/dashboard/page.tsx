"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { startDemoSession, ingestTick, API_BASE_URL } from "@/lib/api";
import type { AlertPayload, L1Tick } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import RiskGauge from "@/components/caregiver/RiskGauge";
import SignalSparkline from "@/components/caregiver/SignalSparkline";
import AlertFeedPanel from "@/components/caregiver/AlertFeedPanel";

type Scenario = "calm" | "escalating" | "rapid_spike";
type ModelType = "full" | "wearable";

const SCENARIO_LABELS: Record<Scenario, string> = {
  calm: "Calm",
  escalating: "Escalating",
  rapid_spike: "Rapid Spike",
};

const BUFFER_SIZE = 12;

function emptyBuffer(): number[] {
  return [];
}

export default function DashboardPage() {
  const [userId, setUserId] = useState<string | null>(null);
  const [modelType, setModelType] = useState<ModelType>("full");
  const [scenario, setScenario] = useState<Scenario>("escalating");
  const [isRunning, setIsRunning] = useState(false);
  const [sendNotifications, setSendNotifications] = useState(false);
  const [latestTick, setLatestTick] = useState<L1Tick | null>(null);
  const [alertList, setAlertList] = useState<AlertPayload[]>([]);

  // Sparkline buffers as refs to avoid re-renders on every tick
  const gsrBuf = useRef<number[]>(emptyBuffer());
  const accBuf = useRef<number[]>(emptyBuffer());
  const tempBuf = useRef<number[]>(emptyBuffer());
  const gsrPeakIndices = useRef<number[]>([]);

  // State copies of buffers for rendering
  const [gsrData, setGsrData] = useState<number[]>([]);
  const [accData, setAccData] = useState<number[]>([]);
  const [tempData, setTempData] = useState<number[]>([]);
  const [peakIndices, setPeakIndices] = useState<number[]>([]);

  const esRef = useRef<EventSource | null>(null);

  // Load user id once
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setUserId(data.user?.id ?? null);
    });
  }, []);

  function pushToBuffer(buf: React.MutableRefObject<number[]>, value: number) {
    buf.current = [...buf.current, value].slice(-BUFFER_SIZE);
  }

  const stopDemo = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setIsRunning(false);
  }, []);

  async function startDemo() {
    if (!userId) return;
    setIsRunning(true);
    setLatestTick(null);
    setAlertList([]);
    gsrBuf.current = [];
    accBuf.current = [];
    tempBuf.current = [];
    gsrPeakIndices.current = [];
    setGsrData([]);
    setAccData([]);
    setTempData([]);
    setPeakIndices([]);

    let sessionId: string;
    try {
      const res = await startDemoSession(userId, scenario, modelType);
      sessionId = res.demo_session_id;
    } catch (err) {
      console.error("Failed to start demo session", err);
      setIsRunning(false);
      return;
    }

    const es = new EventSource(`${API_BASE_URL}/predict/stream/${sessionId}`);
    esRef.current = es;

    es.onmessage = async (e) => {
      let tick: L1Tick & { done?: boolean };
      try {
        tick = JSON.parse(e.data);
      } catch {
        return;
      }

      if (tick.done) {
        es.close();
        esRef.current = null;
        setIsRunning(false);
        return;
      }

      setLatestTick(tick);

      // Update sparkline buffers
      const gsr = tick.features["gsr_phasic_peak_count"] ?? 0;
      const acc = tick.features["acc_svm_mean"] ?? 0;
      const temp = tick.features["skin_temp_mean"] ?? 0;

      pushToBuffer(gsrBuf, gsr);
      pushToBuffer(accBuf, acc);
      pushToBuffer(tempBuf, temp);

      // Mark GSR peaks (high gsr phasic count relative to buffer median)
      const bufCopy = [...gsrBuf.current];
      const sorted = [...bufCopy].sort((a, b) => a - b);
      const median = sorted[Math.floor(sorted.length / 2)] ?? 0;
      const lastIdx = bufCopy.length - 1;
      if (gsr > median * 1.3) {
        gsrPeakIndices.current = [...gsrPeakIndices.current, lastIdx].slice(-BUFFER_SIZE);
      }

      setGsrData([...gsrBuf.current]);
      setAccData([...accBuf.current]);
      setTempData([...tempBuf.current]);
      setPeakIndices([...gsrPeakIndices.current]);

      // Fire-and-forget coordinator ingest
      // sendNotifications overrides demo=false so the coordinator sends real emails
      ingestTick({ ...tick, user_id: userId!, demo: !sendNotifications }).then((alert) => {
        if (alert?.alert_id) {
          setAlertList((prev) => [alert, ...prev]);
        }
      });
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setIsRunning(false);
    };
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const riskScore = latestTick?.risk_score ?? 0;
  const causeTags = latestTick?.cause_tags ?? [];

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Header controls */}
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-6 border-b bg-background/95 backdrop-blur px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Model</span>
          <div className="flex rounded-lg border bg-muted p-1 gap-1">
            {(["full", "wearable"] as ModelType[]).map((m) => (
              <button
                key={m}
                onClick={() => setModelType(m)}
                disabled={isRunning}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                  modelType === m
                    ? "bg-[#282079] text-white shadow-sm"
                    : "text-muted-foreground hover:bg-background"
                }`}
              >
                {m === "full" ? "Controlled Environment" : "Wearable Only"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Scenario</span>
          <div className="flex rounded-lg border bg-muted p-1 gap-1">
            {(Object.keys(SCENARIO_LABELS) as Scenario[]).map((s) => (
              <button
                key={s}
                onClick={() => setScenario(s)}
                disabled={isRunning}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                  scenario === s
                    ? "bg-[#282079] text-white shadow-sm"
                    : "text-muted-foreground hover:bg-background"
                }`}
              >
                {SCENARIO_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        <Button
          size="sm"
          variant={isRunning ? "outline" : "default"}
          onClick={isRunning ? stopDemo : startDemo}
          disabled={!userId}
        >
          {isRunning ? "Stop" : "Start"}
        </Button>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <div
            onClick={() => !isRunning && setSendNotifications((v) => !v)}
            className={`relative h-5 w-9 rounded-full transition-colors ${
              sendNotifications ? "bg-primary" : "bg-muted"
            } ${isRunning ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <span
              className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                sendNotifications ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            Send notifications
          </span>
        </label>

        {isRunning && (
          <Badge variant="secondary" className="text-xs">
            {sendNotifications ? "Live Mode" : "Demo Mode"}
          </Badge>
        )}
      </div>

      {/* Main grid */}
      <div className="grid gap-6 p-6 lg:grid-cols-3">
        {/* Col 1: Gauge */}
        <div className="flex flex-col gap-4 rounded-lg border bg-card p-5 shadow-sm">
          <p className="text-sm font-medium">Stress Escalation Risk</p>
          <div className="flex justify-center">
            <RiskGauge
              riskScore={riskScore}
              severity={latestTick ? (riskScore >= 0.65 ? "high" : riskScore >= 0.35 ? "medium" : "low") : null}
              causeTags={causeTags}
              modelType={modelType}
              isDemo={isRunning}
            />
          </div>
        </div>

        {/* Col 2: Sparklines */}
        <div className="flex flex-col gap-4 rounded-lg border bg-card p-5 shadow-sm">
          <p className="text-sm font-medium">Physiological Signals</p>
          <div className="flex flex-col gap-4">
            <SignalSparkline
              label="GSR Phasic Peaks"
              data={gsrData}
              color="#6366f1"
              unit="peaks"
              peakIndices={peakIndices}
            />
            <SignalSparkline
              label="Acceleration (SVM)"
              data={accData}
              color="#0ea5e9"
              unit="g"
            />
            <SignalSparkline
              label="Skin Temperature"
              data={tempData}
              color="#f59e0b"
              unit="°C"
            />
          </div>
        </div>

        {/* Col 3: Alert feed */}
        <div className="rounded-lg border bg-card p-5 shadow-sm overflow-y-auto max-h-[600px]">
          <AlertFeedPanel alertList={alertList} userId={userId ?? ""} />
        </div>
      </div>
    </div>
  );
}
