"use client";

import { useEffect, useState, useCallback, useContext } from "react";
import { useParams, useRouter } from "next/navigation";
import { sendTurn, startSession, fetchSessionResume } from "@/lib/api";
import { useUser } from "@/hooks/use-user";
import type { ChatMsg } from "@/components/coaching/chat-message";
import SessionHeader from "@/components/coaching/session-header";
import ScenarioInfo from "@/components/coaching/scenario-info";
import ChatArea from "@/components/coaching/chat-area";
import ChatInput from "@/components/coaching/chat-input";
import { Button } from "@/components/ui/button";
import { AlertQueueContext } from "@/context/alert-queue-context";

interface SessionMeta {
  sessionId: string;
  scenarioId: string;
  scenarioTitle: string;
  personaName: string;
  domain: string;
  difficulty: number;
}

export default function SessionPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { user } = useUser();
  const alertCtx = useContext(AlertQueueContext);

  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [turnNumber, setTurnNumber] = useState(1);
  const [turnsRemaining, setTurnsRemaining] = useState(12);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    async function loadSession() {
      const stored = sessionStorage.getItem(`session_${params.sessionId}`);

      // Seed meta from sessionStorage for immediate render while the API call is in flight
      if (stored) {
        try {
          const data = JSON.parse(stored) as {
            scenario_id: string;
            scenario_title: string;
            persona_name: string;
            domain: string;
            difficulty: number;
          };
          setMeta({
            sessionId: params.sessionId,
            scenarioId: data.scenario_id,
            scenarioTitle: data.scenario_title,
            personaName: data.persona_name,
            domain: data.domain,
            difficulty: data.difficulty,
          });
        } catch {}
      }

      // Always load authoritative history from backend
      try {
        const resume = await fetchSessionResume(params.sessionId);

        sessionStorage.setItem(
          `session_${params.sessionId}`,
          JSON.stringify({
            scenario_id: resume.scenario_id,
            scenario_title: resume.scenario_title,
            opening_line: resume.opening_line,
            persona_name: resume.persona_name,
            domain: resume.domain,
            difficulty: resume.difficulty,
          }),
        );

        setMeta({
          sessionId: params.sessionId,
          scenarioId: resume.scenario_id,
          scenarioTitle: resume.scenario_title,
          personaName: resume.persona_name,
          domain: resume.domain,
          difficulty: resume.difficulty,
        });

        const msgs: ChatMsg[] = [
          { id: "opening", role: "persona", text: resume.opening_line },
        ];
        for (const t of resume.turns) {
          msgs.push({ id: `user-${t.turn_number}`, role: "user", text: t.user_text });
          msgs.push({
            id: `persona-${t.turn_number}`,
            role: "persona",
            text: t.persona_reply,
            critic: t.critic_json ?? undefined,
            intent: t.intent_class ?? undefined,
          });
        }
        setMessages(msgs);
        if (resume.turn_count > 0) {
          setTurnNumber(resume.turn_count);
          setTurnsRemaining(resume.max_turns - resume.turn_count);
        }
      } catch (err) {
        // 404 means the session is completed — send to summary
        if (err instanceof Error && err.message.startsWith("API 404:")) {
          router.push(`/coaching/${params.sessionId}/summary`);
          return;
        }
        // other errors — best-effort fallback to sessionStorage opening line
        if (!stored) {
          setLoadError(true);
          return;
        }
        try {
          const data = JSON.parse(stored) as { opening_line?: string };
          if (data.opening_line) {
            setMessages([{ id: "opening", role: "persona", text: data.opening_line }]);
          } else {
            setLoadError(true);
          }
        } catch {
          setLoadError(true);
        }
      }
    }

    loadSession();
  }, [params.sessionId]);

  const handleSend = useCallback(
    async (text: string) => {
      if (!meta || isLoading) return;

      const userMsg: ChatMsg = {
        id: `user-${Date.now()}`,
        role: "user",
        text,
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      alertCtx?.setIsInTurn(true);

      try {
        const res = await sendTurn(meta.sessionId, text);

        if (res.intent === "DISTRESS") {
          router.push("/safe-response");
          return;
        }

        const personaMsg: ChatMsg = {
          id: `persona-${Date.now()}`,
          role: "persona",
          text: res.persona_reply,
          critic: res.critic,
          intent: res.intent,
        };

        setMessages((prev) => [...prev, personaMsg]);
        setTurnNumber(res.turn_number);
        setTurnsRemaining(res.turns_remaining);
        setSessionComplete(res.session_complete);
      } catch {
        const errorMsg: ChatMsg = {
          id: `error-${Date.now()}`,
          role: "persona",
          text: "Something went wrong. Please try again.",
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        alertCtx?.setIsInTurn(false);
        setIsLoading(false);
      }
    },
    [meta, isLoading, router, alertCtx],
  );

  async function handleRestart() {
    if (!meta || !user) return;
    if (!window.confirm("Restart this conversation?")) return;

    try {
      const res = await startSession(user.id, meta.scenarioId);
      sessionStorage.setItem(
        `session_${res.session_id}`,
        JSON.stringify({
          scenario_id: meta.scenarioId,
          scenario_title: meta.scenarioTitle,
          opening_line: res.opening_line,
          persona_name: meta.personaName,
          domain: meta.domain,
          difficulty: meta.difficulty,
        }),
      );
      router.push(`/coaching/${res.session_id}`);
    } catch {}
  }

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-muted-foreground">
          Could not load this session.
        </p>
        <Button variant="outline" onClick={() => router.push("/coaching")}>
          Back to scenarios
        </Button>
      </div>
    );
  }

  if (!meta) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <SessionHeader
        title={meta.scenarioTitle}
        domain={meta.domain}
        difficulty={meta.difficulty}
        turnNumber={turnNumber}
        turnsRemaining={turnsRemaining}
        showInfo={showInfo}
        onToggleInfo={() => setShowInfo(!showInfo)}
        onRestart={handleRestart}
      />

      {showInfo && <ScenarioInfo scenarioId={meta.scenarioId} />}

      <ChatArea
        messages={messages}
        personaName={meta.personaName}
        domain={meta.domain}
      />

      {sessionComplete ? (
        <div className="border-t bg-card px-4 py-4">
          <div className="mx-auto max-w-2xl text-center">
            <p className="mb-3 text-sm font-medium">Session complete</p>
            <Button
              onClick={() =>
                router.push(`/coaching/${meta.sessionId}/summary`)
              }
            >
              View your summary
            </Button>
          </div>
        </div>
      ) : (
        <ChatInput
          onSend={handleSend}
          disabled={isLoading || sessionComplete}
          loading={isLoading}
        />
      )}
    </div>
  );
}
