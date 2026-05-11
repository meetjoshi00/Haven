import type {
  ActiveSession,
  AlertDetail,
  AlertListItem,
  AlertPayload,
  L1Tick,
  Scenario,
  ScenarioDetail,
  SessionEndResponse,
  SessionResumeData,
  SessionStartResponse,
  SessionTurnResponse,
  UserProfileExtended,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

export function fetchScenarios(filters?: {
  domain?: string;
  difficulty?: number;
}): Promise<Scenario[]> {
  const params = new URLSearchParams();
  if (filters?.domain) params.set("domain", filters.domain);
  if (filters?.difficulty != null)
    params.set("difficulty", String(filters.difficulty));
  const qs = params.toString();
  return apiFetch(`/coach/scenarios${qs ? `?${qs}` : ""}`);
}

export function fetchScenario(id: string): Promise<ScenarioDetail> {
  return apiFetch(`/coach/scenarios/${encodeURIComponent(id)}`);
}

export function startSession(
  userId: string,
  scenarioId: string
): Promise<SessionStartResponse> {
  return apiFetch("/coach/session/start", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, scenario_id: scenarioId }),
  });
}

export function sendTurn(
  sessionId: string,
  userText: string
): Promise<SessionTurnResponse> {
  return apiFetch("/coach/session/turn", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, user_text: userText }),
  });
}

export async function fetchActiveSession(
  userId: string,
  scenarioId: string,
): Promise<ActiveSession | null> {
  try {
    return await apiFetch<ActiveSession>(
      `/coach/session/active?user_id=${encodeURIComponent(userId)}&scenario_id=${encodeURIComponent(scenarioId)}`,
    );
  } catch {
    return null;
  }
}

export function fetchSessionResume(sessionId: string): Promise<SessionResumeData> {
  return apiFetch<SessionResumeData>(
    `/coach/session/${encodeURIComponent(sessionId)}/resume`,
  );
}

export function endSession(
  sessionId: string
): Promise<SessionEndResponse> {
  return apiFetch("/coach/session/end", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ---------------------------------------------------------------------------
// L2 — caregiver dashboard API
// ---------------------------------------------------------------------------

export function startDemoSession(
  userId: string,
  scenario: string,
  modelType: "full" | "wearable",
): Promise<{ demo_session_id: string }> {
  return apiFetch("/predict/scenario/start", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, scenario, model_type: modelType }),
  });
}

export async function ingestTick(payload: L1Tick): Promise<AlertPayload | null> {
  try {
    return await apiFetch<AlertPayload | null>("/coordinator/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch {
    return null;
  }
}

export function fetchAlerts(
  userId: string,
  opts?: { limit?: number; offset?: number; severity?: string },
): Promise<AlertListItem[]> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.severity) params.set("severity", opts.severity);
  const qs = params.toString();
  return apiFetch(`/alerts/${encodeURIComponent(userId)}${qs ? `?${qs}` : ""}`);
}

export function fetchAlertDetail(alertId: string): Promise<AlertDetail> {
  return apiFetch(`/alerts/${encodeURIComponent(alertId)}/detail`);
}

export function acknowledgeAlert(
  alertId: string,
  acknowledgedBy: "user" | "caregiver",
): Promise<void> {
  return apiFetch(`/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
  });
}

export function reportFalseAlarm(
  alertId: string,
  reportedBy: string,
  notes?: string,
): Promise<void> {
  return apiFetch(`/alerts/${encodeURIComponent(alertId)}/false-alarm`, {
    method: "POST",
    body: JSON.stringify({ reported_by: reportedBy, notes: notes ?? null }),
  });
}

export async function fetchUserProfile(
  userId: string,
): Promise<UserProfileExtended | null> {
  try {
    return await apiFetch<UserProfileExtended>(
      `/coordinator/profile/${encodeURIComponent(userId)}`,
    );
  } catch {
    return null;
  }
}

export function updateUserProfile(
  userId: string,
  data: Partial<Omit<UserProfileExtended, "user_id">>,
): Promise<UserProfileExtended> {
  return apiFetch(`/coordinator/profile/${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
