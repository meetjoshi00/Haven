import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import CriticFeedback from "@/components/coaching/critic-feedback";

describe("CriticFeedback", () => {
  it("renders score and suggestion", () => {
    render(<CriticFeedback critic={{ score: 4, suggestion: "Try being more specific." }} />);
    expect(screen.getByText(/Score: 4 out of 5/)).toBeInTheDocument();
    expect(screen.getByText("Try being more specific.")).toBeInTheDocument();
  });

  it("renders with score only (no suggestion)", () => {
    render(<CriticFeedback critic={{ score: 3, suggestion: null }} />);
    expect(screen.getByText(/Score: 3 out of 5/)).toBeInTheDocument();
    expect(screen.queryByText(/Try/)).not.toBeInTheDocument();
  });

  it("renders with suggestion only (no score)", () => {
    render(<CriticFeedback critic={{ score: null, suggestion: "Good start." }} />);
    expect(screen.getByText("Good start.")).toBeInTheDocument();
    expect(screen.queryByText(/Score:/)).not.toBeInTheDocument();
  });

  it("renders nothing when both score and suggestion are null", () => {
    const { container } = render(
      <CriticFeedback critic={{ score: null, suggestion: null }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when critic fields are undefined", () => {
    const { container } = render(<CriticFeedback critic={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
