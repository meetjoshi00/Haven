import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchScenarios, fetchScenario, startSession, sendTurn, endSession } from "@/lib/api";

const mockFetch = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function ok(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(""),
  } as Response);
}

function fail(status: number, text: string) {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(text),
  } as Response);
}

describe("fetchScenarios", () => {
  it("calls /coach/scenarios with no params when no filters", async () => {
    mockFetch.mockReturnValueOnce(ok([]));
    await fetchScenarios();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/coach/scenarios"),
      expect.any(Object)
    );
    const url: string = mockFetch.mock.calls[0][0];
    expect(url).not.toContain("?");
  });

  it("appends domain filter to query string", async () => {
    mockFetch.mockReturnValueOnce(ok([]));
    await fetchScenarios({ domain: "social" });
    const url: string = mockFetch.mock.calls[0][0];
    expect(url).toContain("domain=social");
  });

  it("appends difficulty filter to query string", async () => {
    mockFetch.mockReturnValueOnce(ok([]));
    await fetchScenarios({ difficulty: 2 });
    const url: string = mockFetch.mock.calls[0][0];
    expect(url).toContain("difficulty=2");
  });

  it("throws on non-2xx response", async () => {
    mockFetch.mockReturnValueOnce(fail(500, "Internal Server Error"));
    await expect(fetchScenarios()).rejects.toThrow("API 500");
  });
});

describe("fetchScenario", () => {
  it("encodes the scenario ID in the URL", async () => {
    mockFetch.mockReturnValueOnce(ok({ id: "abc" }));
    await fetchScenario("abc 123");
    const url: string = mockFetch.mock.calls[0][0];
    expect(url).toContain("abc%20123");
  });
});

describe("startSession", () => {
  it("sends user_id and scenario_id in POST body", async () => {
    mockFetch.mockReturnValueOnce(
      ok({ session_id: "s1", opening_line: "Hi", scenario_title: "Test" })
    );
    await startSession("user-1", "scenario-1");
    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe("POST");
    const body = JSON.parse(options.body);
    expect(body).toEqual({ user_id: "user-1", scenario_id: "scenario-1" });
  });
});

describe("sendTurn", () => {
  it("sends session_id and user_text in POST body", async () => {
    mockFetch.mockReturnValueOnce(
      ok({
        intent: "ROLEPLAY_TURN",
        persona_reply: "Hello",
        critic: null,
        turn_number: 1,
        turns_remaining: 11,
        session_complete: false,
      })
    );
    await sendTurn("session-1", "Hello there");
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body).toEqual({ session_id: "session-1", user_text: "Hello there" });
  });
});

describe("endSession", () => {
  it("sends session_id in POST body", async () => {
    mockFetch.mockReturnValueOnce(
      ok({ summary: "Good job", avg_score: 4.2, skills_practiced: ["ordering"] })
    );
    await endSession("session-1");
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body).toEqual({ session_id: "session-1" });
  });
});
