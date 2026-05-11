"use client";

import { Coffee, Ear, Briefcase, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CriticSchema } from "@/lib/types";
import CriticFeedback from "./critic-feedback";

const DOMAIN_ICONS: Record<string, LucideIcon> = {
  social: Coffee,
  sensory: Ear,
  workplace: Briefcase,
};

const DOMAIN_BG: Record<string, string> = {
  social: "bg-domain-social-light text-domain-social",
  sensory: "bg-domain-sensory-light text-domain-sensory",
  workplace: "bg-domain-workplace-light text-domain-workplace",
};

export interface ChatMsg {
  id: string;
  role: "persona" | "user";
  text: string;
  critic?: CriticSchema | null;
  intent?: string;
}

interface ChatMessageProps {
  message: ChatMsg;
  personaName: string;
  domain: string;
}

export default function ChatMessage({
  message,
  personaName,
  domain,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end gap-2">
        <div className="max-w-[75%]">
          <p className="mb-1 text-right text-xs text-muted-foreground">You</p>
          <div className="rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
            {message.text}
          </div>
        </div>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
          U
        </div>
      </div>
    );
  }

  const Icon = DOMAIN_ICONS[domain] ?? Coffee;
  const bgClass = DOMAIN_BG[domain] ?? DOMAIN_BG.social;

  return (
    <div className="flex gap-2">
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          bgClass
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="max-w-[75%]">
        <p className="mb-1 text-xs text-muted-foreground">{personaName}</p>
        <div className="rounded-2xl rounded-tl-sm bg-card px-4 py-2.5 text-sm shadow-sm ring-1 ring-border">
          {message.text}
        </div>
        {message.intent === "ROLEPLAY_TURN" && message.critic && (
          <CriticFeedback critic={message.critic} />
        )}
      </div>
    </div>
  );
}
