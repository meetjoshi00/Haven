"use client";

import { acknowledgeAlert, reportFalseAlarm } from "@/lib/api";
import type { AlertPayload } from "@/lib/types";

interface Props {
  alert: AlertPayload;
  onDismiss: () => void;
}

export default function AlertOverlay({ alert, onDismiss }: Props) {
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
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="alert-overlay-headline"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
    >
      <div className="w-full max-w-md rounded-xl bg-orange-50 p-6 shadow-xl">
        <p
          id="alert-overlay-headline"
          className="mb-2 text-lg font-semibold text-orange-900"
        >
          {alert.headline}
        </p>
        <p className="mb-3 text-sm text-orange-800">{alert.person_message}</p>
        <p className="mb-6 text-xs text-orange-700">
          Your emergency contact has been notified.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            onClick={handleFalseAlarm}
            className="flex-1 rounded-md border border-orange-300 bg-white px-4 py-2 text-sm font-medium text-orange-900 hover:bg-orange-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
          >
            I&apos;m okay — false alarm
          </button>
          <button
            onClick={handleAcknowledge}
            className="flex-1 rounded-md bg-orange-700 px-4 py-2 text-sm font-medium text-white hover:bg-orange-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
          >
            Noted, thank you
          </button>
        </div>
      </div>
    </div>
  );
}
