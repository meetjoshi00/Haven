import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SessionHeader from "@/components/coaching/session-header";

const defaultProps = {
  title: "Ordering at a café",
  domain: "social",
  difficulty: 1,
  turnNumber: 3,
  turnsRemaining: 9,
  showInfo: false,
  onToggleInfo: vi.fn(),
  onRestart: vi.fn(),
};

describe("SessionHeader", () => {
  it("renders the scenario title", () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText("Ordering at a café")).toBeInTheDocument();
  });

  it("shows domain badge", () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText("Social")).toBeInTheDocument();
  });

  it("shows difficulty badge", () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText("Beginner")).toBeInTheDocument();
  });

  it("shows turn counter", () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText(/Turn 3/)).toBeInTheDocument();
    expect(screen.getByText(/9 left/)).toBeInTheDocument();
  });

  it("calls onToggleInfo when info button is clicked", async () => {
    const onToggleInfo = vi.fn();
    render(<SessionHeader {...defaultProps} onToggleInfo={onToggleInfo} />);
    await userEvent.click(screen.getByLabelText("Toggle scenario info"));
    expect(onToggleInfo).toHaveBeenCalledOnce();
  });

  it("calls onRestart when restart button is clicked", async () => {
    const onRestart = vi.fn();
    render(<SessionHeader {...defaultProps} onRestart={onRestart} />);
    await userEvent.click(screen.getByLabelText("Restart conversation"));
    expect(onRestart).toHaveBeenCalledOnce();
  });

  it("renders all difficulty levels correctly", () => {
    const levels: [number, string][] = [
      [1, "Beginner"],
      [2, "Intermediate"],
      [3, "Advanced"],
    ];
    for (const [difficulty, label] of levels) {
      const { unmount } = render(
        <SessionHeader {...defaultProps} difficulty={difficulty} />
      );
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });
});
