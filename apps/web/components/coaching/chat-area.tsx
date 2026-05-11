"use client";

import { useEffect, useRef } from "react";
import ChatMessage, { type ChatMsg } from "./chat-message";

interface ChatAreaProps {
  messages: ChatMsg[];
  personaName: string;
  domain: string;
}

export default function ChatArea({
  messages,
  personaName,
  domain,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div
      className="flex-1 overflow-y-auto px-4 py-4"
      aria-live="polite"
      aria-label="Chat messages"
    >
      <div className="mx-auto max-w-2xl space-y-4">
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            personaName={personaName}
            domain={domain}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
