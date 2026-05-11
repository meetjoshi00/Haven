import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatInput from "@/components/coaching/chat-input";

describe("ChatInput", () => {
  it("renders the textarea and send button", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send message/i })).toBeInTheDocument();
  });

  it("calls onSend with trimmed text on Enter", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello there{Enter}");
    expect(onSend).toHaveBeenCalledWith("Hello there");
  });

  it("does not call onSend on Shift+Enter", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello{Shift>}{Enter}{/Shift}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend with blank input", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables textarea and button when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("shows hint text", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByText(/Press Enter to send/i)).toBeInTheDocument();
  });

  it("clears the input after send", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    await userEvent.type(textarea, "My reply{Enter}");
    expect(textarea.value).toBe("");
  });
});
