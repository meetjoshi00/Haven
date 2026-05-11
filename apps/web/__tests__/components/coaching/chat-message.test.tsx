import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChatMessage from "@/components/coaching/chat-message";
import type { ChatMsg } from "@/components/coaching/chat-message";

const userMsg: ChatMsg = {
  id: "u1",
  role: "user",
  text: "Hello, I'd like a coffee please.",
};

const personaMsg: ChatMsg = {
  id: "p1",
  role: "persona",
  text: "Sure! What size would you like?",
  intent: "ROLEPLAY_TURN",
  critic: { score: 4, suggestion: "Good greeting!" },
};

const personaNocritic: ChatMsg = {
  id: "p2",
  role: "persona",
  text: "Let me help you with that.",
  intent: "OFF_TOPIC",
  critic: null,
};

describe("ChatMessage — user", () => {
  it("renders the user's message text", () => {
    render(<ChatMessage message={userMsg} personaName="Maya" domain="social" />);
    expect(screen.getByText("Hello, I'd like a coffee please.")).toBeInTheDocument();
  });

  it("shows 'You' label", () => {
    render(<ChatMessage message={userMsg} personaName="Maya" domain="social" />);
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("does not show persona name for user message", () => {
    render(<ChatMessage message={userMsg} personaName="Maya" domain="social" />);
    expect(screen.queryByText("Maya")).not.toBeInTheDocument();
  });
});

describe("ChatMessage — persona", () => {
  it("renders the persona message text", () => {
    render(<ChatMessage message={personaMsg} personaName="Maya" domain="social" />);
    expect(screen.getByText("Sure! What size would you like?")).toBeInTheDocument();
  });

  it("shows persona name label", () => {
    render(<ChatMessage message={personaMsg} personaName="Maya" domain="social" />);
    expect(screen.getByText("Maya")).toBeInTheDocument();
  });

  it("shows critic feedback for ROLEPLAY_TURN intent", () => {
    render(<ChatMessage message={personaMsg} personaName="Maya" domain="social" />);
    expect(screen.getByText(/Score: 4 out of 5/)).toBeInTheDocument();
    expect(screen.getByText("Good greeting!")).toBeInTheDocument();
  });

  it("does not show critic for OFF_TOPIC intent even if critic is null", () => {
    render(<ChatMessage message={personaNocritic} personaName="Maya" domain="social" />);
    expect(screen.queryByText(/Score:/)).not.toBeInTheDocument();
  });
});
