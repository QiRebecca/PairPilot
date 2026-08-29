import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("PairPilot app", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts with the intent composer and no installed request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          product: "PairPilot",
          executionMode: "LIVE GEMINI + GOOGLE ADK + A2A",
          exactModelId: "gemini-3.7-flash",
          activeIntent: null,
          intentRegistry: [],
          peerIntents: [],
          intentPairSessions: [],
          run: null,
          turns: [],
          messages: [],
          beliefs: [],
          proposals: [],
          holds: [],
          approvalRequests: [],
          approvals: [],
          matches: [],
          relationships: [],
          relationshipEvents: [],
          memories: [],
          protectedMemoryCount: 1,
        }),
      }),
    );
    render(<App />);
    expect(await screen.findByText("gemini-3.7-flash")).toBeInTheDocument();
    expect(screen.getByText("What are you looking for?")).toBeInTheDocument();
    expect(screen.getByText("Draft with my agent")).toBeDisabled();
    expect(screen.queryByText("Start agent monitoring")).not.toBeInTheDocument();
  });

  it("gives a matched user a clear path back to the request composer", async () => {
    const empty = {
      product: "PairPilot", executionMode: "LIVE GEMINI + GOOGLE ADK + A2A", exactModelId: "gemini-3.7-flash",
      activeIntent: null, intentRegistry: [], peerIntents: [], intentPairSessions: [], run: null, turns: [], messages: [], beliefs: [], proposals: [], holds: [], approvalRequests: [], approvals: [], matches: [], relationships: [], relationshipEvents: [], memories: [], protectedMemoryCount: 1,
    };
    const matched = {
      ...empty,
      activeIntent: { intent_id: "intent-qi", owner_agent_id: "qi-agent", public_title: "ICML roommate", status: "MATCHED" },
      run: { runId: "run-1", status: "COMMITTED" },
      matches: [{ matchId: "match-1", candidateAgentId: "maya-agent" }],
    };
    let stateReads = 0;
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/demo/state") {
        const payload = stateReads++ === 0 ? matched : empty;
        return { ok: true, json: async () => payload };
      }
      if (path === "/api/demo/reset") return { ok: true, json: async () => ({ status: "RESET" }) };
      throw new Error(`Unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(<App />);
    expect(await screen.findByText("You’re matched with Maya")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start a new request" }));

    expect(await screen.findByText("What are you looking for?")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/demo/reset", expect.objectContaining({ method: "POST" }));
  });

  it("publishing immediately starts Qi's multi-agent workflow", async () => {
    const draftIntent = {
      intent_id: "intent-qi-draft", owner_agent_id: "qi-agent", public_title: "Looking for an ICML roommate", public_summary: "Share a room in Seoul.",
      public_constraints: { event: "ICML", location: "Seoul", date_start: "2026-07-06", date_end: "2026-07-10", roommate_gender_preference: "female" },
      public_requirements: ["ICML attendee"], status: "DRAFT", version: 1,
    };
    const openIntent = { ...draftIntent, status: "OPEN", version: 2 };
    const baseState = {
      product: "PairPilot", executionMode: "LIVE GEMINI + GOOGLE ADK + A2A", exactModelId: "gemini-3.7-flash",
      intentRegistry: [], peerIntents: [], intentPairSessions: [], run: null, turns: [], messages: [], beliefs: [], proposals: [], holds: [], approvalRequests: [], approvals: [], matches: [], relationships: [], relationshipEvents: [], memories: [], protectedMemoryCount: 1,
    };
    const review = {
      publicPost: draftIntent,
      agentOnly: { quiet_overnight_compatibility: { importance: "high", source: "explicit_user_input" }, maximum_additional_cost_usd: 70, partial_date_overlap_allowed: true },
      protected: { count: 1, summary: "Protected fact", disclosure: "Never included in public posts or peer-agent messages" },
      fieldProvenance: {}, uncertainties: [],
    };
    let stateReads = 0;
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/demo/state") {
        const payload = { ...baseState, activeIntent: stateReads++ === 0 ? draftIntent : openIntent };
        return { ok: true, json: async () => payload };
      }
      if (path === "/api/intents/intent-qi-draft/review") return { ok: true, json: async () => review };
      if (path === "/api/intents/publish") return { ok: true, json: async () => ({ status: "OPEN", intent: openIntent, created: true }) };
      throw new Error(`Unexpected request: ${path}`);
    }));
    class MockEventSource {
      static latestUrl = "";
      onerror: (() => void) | null = null;
      constructor(url: string | URL) { MockEventSource.latestUrl = String(url); }
      addEventListener() {}
      close() {}
    }
    vi.stubGlobal("EventSource", MockEventSource);

    render(<App />);
    expect(await screen.findByText("Review what your agent will publish")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Publish and let my agent handle it" }));

    await waitFor(() => expect(MockEventSource.latestUrl).toBe("/api/demo/run/stream?intent_id=intent-qi-draft"));
  });
});
