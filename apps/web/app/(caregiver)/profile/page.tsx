"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Check } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { fetchUserProfile, updateUserProfile } from "@/lib/api";
import type { UserProfileExtended } from "@/lib/types";
import { useUser } from "@/hooks/use-user";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const PHONE_RE = /^\+[1-9]\d{7,14}$/;

// Values match DB CHECK constraints in user_profiles_extended
const SENSITIVITY_OPTIONS = [
  { value: "q25", label: "Standard (Q25)", description: "default sensitivity" },
  { value: "q50", label: "Moderate (Q50)", description: "fewer alerts" },
  { value: "q75", label: "High Bar (Q75)", description: "only strong signals" },
];

const NOTIFY_EMERGENCY_OPTIONS = [
  { value: "all_alerts", label: "Medium & High" },
  { value: "high_only", label: "High only" },
  { value: "none", label: "Never" },
];

const NOTIFY_SELF_OPTIONS = [
  { value: "all_alerts", label: "All alerts" },
  { value: "none", label: "Never" },
];

const INPUT_CLASS =
  "w-full rounded-lg border border-input bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#282079] transition-shadow placeholder:text-muted-foreground";

function PillToggle({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
            value === opt.value
              ? "border-[#282079] bg-[#282079] text-white"
              : "border-border text-muted-foreground hover:bg-accent/50"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function CustomSelect({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string; description: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = options.find((o) => o.value === value) ?? options[0];

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg border border-input bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#282079]"
      >
        <span>
          {selected.label}{" "}
          <span className="text-muted-foreground">— {selected.description}</span>
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="absolute z-10 mt-1 w-full rounded-lg border border-border bg-white shadow-md">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              className="flex w-full items-center justify-between px-3 py-2.5 text-sm hover:bg-accent/50 first:rounded-t-lg last:rounded-b-lg"
            >
              <span>
                {opt.label}{" "}
                <span className="text-muted-foreground">— {opt.description}</span>
              </span>
              {opt.value === value && <Check className="h-4 w-4 text-[#282079]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProfilePage() {
  const { user } = useUser();
  const [userId, setUserId] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [form, setForm] = useState<Partial<Omit<UserProfileExtended, "user_id">>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) {
      setFullName(
        (user.user_metadata?.full_name as string | undefined) ??
        (user.user_metadata?.name as string | undefined) ??
        ""
      );
    }
  }, [user]);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(async ({ data }) => {
      const uid = data.user?.id;
      if (!uid) return;
      setUserId(uid);
      const profile = await fetchUserProfile(uid);
      setForm({
        phone_number: profile?.phone_number ?? "",
        emergency_contact_name: profile?.emergency_contact_name ?? "",
        emergency_contact_phone: profile?.emergency_contact_phone ?? "",
        emergency_contact_email: profile?.emergency_contact_email ?? "",
        notify_emergency_on: profile?.notify_emergency_on ?? "high_only",
        notify_self_on: profile?.notify_self_on ?? "all_alerts",
        alert_sensitivity: profile?.alert_sensitivity ?? "q25",
      });
      setLoading(false);
    });
  }, []);

  function set(field: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
    setError("");
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!userId) return;

    if (form.phone_number && !PHONE_RE.test(form.phone_number)) {
      setError("Phone must be in E.164 format: +1234567890");
      return;
    }
    if (form.emergency_contact_phone && !PHONE_RE.test(form.emergency_contact_phone)) {
      setError("Emergency contact phone must be in E.164 format: +1234567890");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const supabase = createClient();
      if (fullName) {
        await supabase.auth.updateUser({ data: { full_name: fullName } });
      }
      await updateUserProfile(userId, form);
      setSaved(true);
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg p-6 space-y-8">
      <h1 className="text-lg font-semibold">Profile</h1>

      <form onSubmit={handleSave} className="space-y-8">

        {/* Section 1: Personal */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground">Personal</h2>
          <div className="h-px bg-border" />

          <div className="space-y-1.5">
            <Label htmlFor="full-name">Full name</Label>
            <input
              id="full-name"
              type="text"
              placeholder="Your name"
              value={fullName}
              onChange={(e) => { setFullName(e.target.value); setSaved(false); }}
              className={INPUT_CLASS}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <input
              id="email"
              type="email"
              value={user?.email ?? ""}
              disabled
              className="w-full rounded-lg border border-input bg-white px-3 py-2 text-sm text-muted-foreground opacity-70 cursor-not-allowed"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <input
              id="phone"
              type="tel"
              placeholder="+12025550123"
              value={form.phone_number ?? ""}
              onChange={(e) => set("phone_number", e.target.value)}
              className={INPUT_CLASS}
            />
            <p className="text-xs text-muted-foreground">E.164 format — optional</p>
          </div>
        </section>

        {/* Section 2: Emergency Contact */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground">Emergency Contact</h2>
          <div className="h-px bg-border" />

          <div className="space-y-1.5">
            <Label htmlFor="ec-name">Name</Label>
            <input
              id="ec-name"
              type="text"
              placeholder="Full name"
              value={form.emergency_contact_name ?? ""}
              onChange={(e) => set("emergency_contact_name", e.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ec-email">Email</Label>
            <input
              id="ec-email"
              type="email"
              placeholder="contact@example.com"
              value={form.emergency_contact_email ?? ""}
              onChange={(e) => set("emergency_contact_email", e.target.value)}
              className={INPUT_CLASS}
            />
            <p className="text-xs text-muted-foreground">This email receives alert notifications</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ec-phone">Phone</Label>
            <input
              id="ec-phone"
              type="tel"
              placeholder="+12025550123"
              value={form.emergency_contact_phone ?? ""}
              onChange={(e) => set("emergency_contact_phone", e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
        </section>

        {/* Section 3: Notifications */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground">Notifications</h2>
          <div className="h-px bg-border" />

          <div className="space-y-2">
            <Label>Notify emergency contact on</Label>
            <PillToggle
              options={NOTIFY_EMERGENCY_OPTIONS}
              value={form.notify_emergency_on ?? "high_only"}
              onChange={(v) => set("notify_emergency_on", v)}
            />
          </div>

          <div className="space-y-2">
            <Label>Notify me on</Label>
            <PillToggle
              options={NOTIFY_SELF_OPTIONS}
              value={form.notify_self_on ?? "all_alerts"}
              onChange={(v) => set("notify_self_on", v)}
            />
          </div>

          <div className="space-y-2">
            <Label>Alert sensitivity</Label>
            <CustomSelect
              options={SENSITIVITY_OPTIONS}
              value={form.alert_sensitivity ?? "q25"}
              onChange={(v) => set("alert_sensitivity", v)}
            />
          </div>
        </section>

        {error && <p className="text-sm text-destructive">{error}</p>}
        {saved && <p className="text-sm text-green-700">Saved</p>}

        <Button type="submit" disabled={saving} className="bg-[#282079] hover:bg-[#282079]/90">
          {saving ? "Saving…" : "Save"}
        </Button>
      </form>
    </div>
  );
}
