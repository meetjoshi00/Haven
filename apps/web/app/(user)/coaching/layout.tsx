"use client";

import { useEffect, useState } from "react";
import { ListFilter } from "lucide-react";
import Sidebar from "@/components/layout/sidebar";
import ScenarioPanel from "@/components/coaching/scenario-panel";
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";
import { useUser } from "@/hooks/use-user";
import { useAlertListener } from "@/hooks/use-alert-listener";
import { AlertQueueContext } from "@/context/alert-queue-context";
import AlertBanner from "@/components/coaching/AlertBanner";
import AlertOverlay from "@/components/coaching/AlertOverlay";

export default function CoachingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isInTurn, setIsInTurn] = useState(false);
  const { user } = useUser();
  const { activeAlert, queueLength, consumeNextAlert, dismissAlert } =
    useAlertListener(user?.id);

  useEffect(() => {
    if (!isInTurn && !activeAlert && queueLength > 0) {
      consumeNextAlert();
    }
  }, [isInTurn, queueLength, activeAlert, consumeNextAlert]);

  const isHigh = activeAlert?.severity === "high";

  return (
    <AlertQueueContext.Provider value={{ setIsInTurn }}>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar />

        <main className="flex-1 overflow-y-auto">{children}</main>

        {/* Desktop: inline panel */}
        <div className="hidden w-80 shrink-0 border-l bg-card lg:block">
          <ScenarioPanel />
        </div>

        {/* Mobile/tablet: floating button + sheet drawer */}
        <button
          onClick={() => setDrawerOpen(true)}
          className="fixed bottom-5 right-5 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg lg:hidden"
          aria-label="Open scenarios"
        >
          <ListFilter className="h-5 w-5" />
        </button>

        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="right" className="w-80 p-0">
            <SheetTitle className="sr-only">Scenarios</SheetTitle>
            <ScenarioPanel onSelect={() => setDrawerOpen(false)} />
          </SheetContent>
        </Sheet>

        {activeAlert && !isHigh && !isInTurn && (
          <AlertBanner alert={activeAlert} onDismiss={dismissAlert} />
        )}
        {activeAlert && isHigh && !isInTurn && (
          <AlertOverlay alert={activeAlert} onDismiss={dismissAlert} />
        )}
      </div>
    </AlertQueueContext.Provider>
  );
}
