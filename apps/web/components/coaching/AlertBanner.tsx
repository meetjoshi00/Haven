"use client";

import { acknowledgeAlert, reportFalseAlarm } from "@/lib/api";
import type { AlertPayload } from "@/lib/types";

interface Props {
  alert: AlertPayload;
  onDismiss: () => void;
}

export default function AlertBanner({ alert, onDismiss }: Props) {
  async function handleFalseAlarm() {
    await reportFalseAlarm(alert.alert_id, "user").catch(() => {});
    onDismiss();
  }

  async function handleAcknowledge() {
    await acknowledgeAlert(alert.alert_id, "user").catch(() => {});
    onDismiss();
  }

  return (
    <div
      role="alert"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-amber-200 bg-amber-50 px-4 py-3"
    >
      <div className="mx-auto flex max-w-2xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-semibold text-amber-900">{alert.headline}</p>
          <p className="text-sm text-amber-800">{alert.person_message}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={handleFalseAlarm}
            className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            I&apos;m okay — false alarm
          </button>
          <button
            onClick={handleAcknowledge}
            className="rounded-md bg-amber-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            Noted, thank you
          </button>
        </div>
      </div>
    </div>
  );
}
