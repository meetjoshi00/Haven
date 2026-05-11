export interface Scenario {
  id: string;
  title: string;
  domain: string;
  difficulty: number;
  skills_primary: string[];
  estimated_turns: number;
  reviewed: boolean;
  persona_name: string;
  setting: string;
}

export interface SessionStartResponse {
  session_id: string;
  opening_line: string;
  scenario_title: string;
}

export interface CriticSchema {
  score?: number | null;
  suggestion?: string | null;
}

export interface SessionTurnResponse {
  intent: string;
  persona_reply: string;
  critic?: CriticSchema | null;
  turn_number: number;
  turns_remaining: number;
  session_complete: boolean;
}

export interface SessionEndResponse {
  summary: string;
  avg_score: number;
  skills_practiced: string[];
}

export interface ActiveSession {
  session_id: string;
  turn_count: number;
  max_turns: number;
  started_at: string;
}

export interface TurnData {
  turn_number: number;
  user_text: string;
  persona_reply: string;
  critic_json: { score?: number | null; suggestion?: string | null };
  intent_class?: string | null;
}

export interface SessionResumeData {
  session_id: string;
  scenario_id: string;
  scenario_title: string;
  opening_line: string;
  persona_name: string;
  domain: string;
  difficulty: number;
  turn_count: number;
  max_turns: number;
  turns: TurnData[];
}

export interface ScenarioDetail {
  id: string;
  title: string;
  domain: string;
  difficulty: number;
  persona: string;
  rubric: string;
  setting: string;
  opening_line: string;
  skills_primary: string[];
  tags: string[];
  estimated_turns: number;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// L2 — caregiver dashboard types
// ---------------------------------------------------------------------------

export interface L1Tick {
  risk_score: number;
  cause_tags: string[];
  shap_values: Record<string, number>;
  features: Record<string, number>;
  ts: string;
  user_id: string;
  model_type: "full" | "wearable";
  demo: boolean;
  done?: boolean;
}

export interface AppAction {
  label: string;
  action: "false_alarm" | "acknowledge";
}

export interface AlertPayload {
  alert_id: string;
  user_id: string;
  severity: string;
  risk_score: number;
  cause_tags: string[];
  headline: string;
  person_message: string;
  caregiver_message: string;
  why: string;
  recommended_actions: string[];
  app_actions: AppAction[];
  cooldown_until: string | null;
  rule_id: string;
  demo: boolean;
  ts: string;
}

export interface AlertListItem {
  alert_id: string;
  severity: string;
  headline: string;
  cause_tags: string[];
  acknowledged: boolean;
  false_alarm: boolean;
  demo: boolean;
  ts: string;
}

export interface AlertDetail extends AlertPayload {
  features: Record<string, number>;
  shap_values: Record<string, number>;
  acknowledged: boolean;
  acknowledged_by: string | null;
  false_alarm: boolean;
}

export interface UserProfileExtended {
  user_id: string;
  phone_number: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_email: string | null;
  notify_emergency_on: string | null;
  notify_self_on: string | null;
  alert_sensitivity: string | null;
}
