import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("PairPilot app", () => {
  afterEach(() => vi.restoreAllMocks());

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
});
