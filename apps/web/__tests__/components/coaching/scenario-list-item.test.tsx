import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScenarioListItem from "@/components/coaching/scenario-list-item";
import type { Scenario } from "@/lib/types";

const scenario: Scenario = {
  id: "coffee-order",
  title: "Ordering at a café",
  domain: "social",
  difficulty: 2,
  persona_name: "Maya the barista",
  setting: "A busy coffee shop counter",
  skills_primary: ["ordering", "small talk"],
  estimated_turns: 10,
  reviewed: true,
};

describe("ScenarioListItem", () => {
  it("renders the scenario title", () => {
    render(<ScenarioListItem scenario={scenario} onClick={vi.fn()} />);
    expect(screen.getByText("Ordering at a café")).toBeInTheDocument();
  });

  it("renders the persona name as subtitle", () => {
    render(<ScenarioListItem scenario={scenario} onClick={vi.fn()} />);
    expect(screen.getByText("Maya the barista")).toBeInTheDocument();
  });

  it("renders difficulty dots with correct aria-label", () => {
    render(<ScenarioListItem scenario={scenario} onClick={vi.fn()} />);
    expect(screen.getByLabelText("Difficulty 2 of 3")).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<ScenarioListItem scenario={scenario} onClick={onClick} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled when loading prop is true", () => {
    render(<ScenarioListItem scenario={scenario} onClick={vi.fn()} loading />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("falls back to setting text when persona_name is empty", () => {
    const s = { ...scenario, persona_name: "" };
    render(<ScenarioListItem scenario={s} onClick={vi.fn()} />);
    expect(screen.getByText("A busy coffee shop counter")).toBeInTheDocument();
  });

  it("renders all three domains without crashing", () => {
    const domains = ["social", "sensory", "workplace"] as const;
    for (const domain of domains) {
      const { unmount } = render(
        <ScenarioListItem
          scenario={{ ...scenario, domain }}
          onClick={vi.fn()}
        />
      );
      expect(screen.getByText("Ordering at a café")).toBeInTheDocument();
      unmount();
    }
  });
});
