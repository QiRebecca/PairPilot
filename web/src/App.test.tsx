import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("PairPilot app", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the live model and human commitment boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          product: "PairPilot",
          executionMode: "LIVE GEMINI + GOOGLE ADK + A2A",
          exactModelId: "gemini-3.7-flash",
          goal: "Find a quiet ICML roommate.",
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
    expect(screen.getByText("Human approval required")).toBeInTheDocument();
    expect(screen.getByText("Start live run")).toBeInTheDocument();
  });
});
