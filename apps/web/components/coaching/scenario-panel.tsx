"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Search, RotateCcw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchScenarios, fetchActiveSession, startSession } from "@/lib/api";
import { useUser } from "@/hooks/use-user";
import { DOMAIN_LABELS } from "@/lib/constants";
import type { ActiveSession, Scenario } from "@/lib/types";
import ScenarioListItem from "./scenario-list-item";

const DOMAIN_FILTERS = ["all", "social", "sensory", "workplace"] as const;

interface ScenarioPanelProps {
  onSelect?: () => void;
}

interface PendingResume {
  activeSession: ActiveSession;
  scenario: Scenario;
}

interface PendingSwitch {
  scenario: Scenario;
}

export default function ScenarioPanel({ onSelect }: ScenarioPanelProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [pendingResume, setPendingResume] = useState<PendingResume | null>(null);
  const [pendingSwitch, setPendingSwitch] = useState<PendingSwitch | null>(null);
  const { user } = useUser();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    fetchScenarios()
      .then(setScenarios)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Clear inline prompts when route changes (e.g. after navigation completes)
  useEffect(() => {
    setPendingResume(null);
    setPendingSwitch(null);
  }, [pathname]);

  const filtered = useMemo(() => {
    let list = scenarios;
    if (domain !== "all") {
      list = list.filter((s) => s.domain === domain);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) =>
          s.title.toLowerCase().includes(q) ||
          s.persona_name.toLowerCase().includes(q),
      );
    }
    return list;
  }, [scenarios, domain, search]);

  /** Extract current session's scenario ID if we're inside a session route. */
  function getCurrentSessionScenarioId(): string | null {
    const match = pathname.match(/^\/coaching\/([^/]+)$/);
    if (!match) return null;
    const sessionId = match[1];
    try {
      const raw = sessionStorage.getItem(`session_${sessionId}`);
      if (!raw) return null;
      const data = JSON.parse(raw) as { scenario_id: string };
      return data.scenario_id ?? null;
    } catch {
      return null;
    }
  }

  /** Navigate to a fresh session — shared by "start new" and "start fresh" paths. */
  async function launchNewSession(scenario: Scenario) {
    if (!user) return;
    setStarting(scenario.id);
    try {
      const res = await startSession(user.id, scenario.id);
      sessionStorage.setItem(
        `session_${res.session_id}`,
        JSON.stringify({
          scenario_id: scenario.id,
          scenario_title: res.scenario_title,
          opening_line: res.opening_line,
          persona_name: scenario.persona_name,
          domain: scenario.domain,
          difficulty: scenario.difficulty,
        }),
      );
      onSelect?.();
      router.push(`/coaching/${res.session_id}`);
      setStarting(null);
    } catch {
      setStarting(null);
    }
  }

  async function handleSelect(scenario: Scenario) {
    if (!user || starting || checking) return;

    // Clear any existing prompt first
    setPendingResume(null);
    setPendingSwitch(null);

    const currentScenarioId = getCurrentSessionScenarioId();

    // Case 1: user is already in a session for this same scenario — do nothing
    if (currentScenarioId === scenario.id) return;

    // Case 2: user is in a session for a DIFFERENT scenario — ask to confirm switch
    if (currentScenarioId !== null) {
      setPendingSwitch({ scenario });
      return;
    }

    // Case 3: user is on the home page — check for an existing incomplete session
    setChecking(scenario.id);
    const active = await fetchActiveSession(user.id, scenario.id);
    setChecking(null);

    if (active && active.turn_count < active.max_turns) {
      setPendingResume({ activeSession: active, scenario });
    } else {
      await launchNewSession(scenario);
    }
  }

  async function handleResume(pendingResume: PendingResume) {
    const { activeSession, scenario } = pendingResume;
    setPendingResume(null);
    // Always overwrite so opening_line is empty, which forces the session page
    // to call fetchSessionResume and reconstruct the full turn history.
    sessionStorage.setItem(
      `session_${activeSession.session_id}`,
      JSON.stringify({
        scenario_id: scenario.id,
        scenario_title: scenario.title,
        opening_line: "",
        persona_name: scenario.persona_name,
        domain: scenario.domain,
        difficulty: scenario.difficulty,
      }),
    );
    onSelect?.();
    router.push(`/coaching/${activeSession.session_id}`);
  }

  async function handleStartFresh(scenario: Scenario) {
    setPendingResume(null);
    await launchNewSession(scenario);
  }

  async function handleConfirmSwitch(scenario: Scenario) {
    setPendingSwitch(null);
    if (!user) return;
    const active = await fetchActiveSession(user.id, scenario.id);
    if (active && active.turn_count < active.max_turns) {
      await handleResume({ activeSession: active, scenario });
    } else {
      await launchNewSession(scenario);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-4 pb-3 pt-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Scenarios</h2>
          <span className="text-xs text-muted-foreground">
            {filtered.length} of {scenarios.length}
          </span>
        </div>

        <div className="relative mt-3">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search scenarios..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-sm"
          />
        </div>

        <div className="mt-3 flex gap-1.5">
          {DOMAIN_FILTERS.map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                domain === d
                  ? "bg-[#282079] text-white"
                  : "bg-muted text-muted-foreground hover:bg-accent",
              )}
            >
              {d === "all" ? "All" : (DOMAIN_LABELS[d] ?? d)}
            </button>
          ))}
        </div>
      </div>

      {/* Inline resume prompt */}
      {pendingResume && (
        <div className="border-b bg-muted/40 px-4 py-3">
          <p className="text-xs font-medium text-foreground">
            You have a session in progress
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Turn {pendingResume.activeSession.turn_count} of{" "}
            {pendingResume.activeSession.max_turns} completed
          </p>
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={() => handleResume(pendingResume)}
            >
              Resume
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => handleStartFresh(pendingResume.scenario)}
            >
              <RotateCcw className="mr-1 h-3 w-3" />
              Start fresh
            </Button>
            <button
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setPendingResume(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Inline switch-scenario prompt */}
      {pendingSwitch && (
        <div className="border-b bg-muted/40 px-4 py-3">
          <p className="text-xs font-medium text-foreground">
            Switch scenario?
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            This will leave your current session.
          </p>
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={() => handleConfirmSwitch(pendingSwitch.scenario)}
            >
              Yes, switch
            </Button>
            <button
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setPendingSwitch(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            No scenarios found
          </p>
        ) : (
          <div className="space-y-1">
            {filtered.map((s) => (
              <ScenarioListItem
                key={s.id}
                scenario={s}
                loading={starting === s.id || checking === s.id}
                onClick={() => handleSelect(s)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
