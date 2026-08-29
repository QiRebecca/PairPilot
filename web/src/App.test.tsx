import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { OSBootstrap } from "./types";

function bootstrap(overrides: Partial<OSBootstrap> = {}): OSBootstrap {
  return {
    personalAgent: { agentId: "qi-agent", displayName: "Qi Agent", ownerDisplayName: "Qi", persistentIdentity: true },
    tasks: [], conversations: [{ conversation_id: "conversation_global_qi", kind: "GLOBAL_PERSONAL_AGENT" }],
    conversationMessages: [], decisions: [], candidateAssessments: [], rooms: [], roomMessages: [], presentationDirectives: [], explorePosts: [],
    implementationTruth: { dynamicWorkersImplemented: false, peerHumansAreSynthetic: true, sharedRoomIsSyntheticDemo: true },
    demoState: {
      product: "PairPilot", executionMode: "LIVE GEMINI + GOOGLE ADK + A2A", exactModelId: "gemini-3.7-flash",
      activeIntent: null, intentRegistry: [], peerIntents: [], intentPairSessions: [], run: null, turns: [], messages: [], beliefs: [], proposals: [], holds: [], approvalRequests: [], approvals: [], matches: [], relationships: [], relationshipEvents: [], memories: [], protectedMemoryCount: 1,
    },
    ...overrides,
  };
}

describe("PairPilot Personal Agent OS", () => {
  beforeEach(() => window.history.replaceState({}, "", "/agent"));
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("makes the persistent Qi conversation the default product surface", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => bootstrap() }));
    render(<App />);
    expect(await screen.findByText("What can I take care of?")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message Qi Agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New request" })).toBeInTheDocument();
    expect(screen.getByText("Your persistent Personal Agent")).toBeInTheDocument();
  });

  it("keeps task conversations isolated by conversation id", async () => {
    window.history.replaceState({}, "", "/requests/task-icml");
    const data = bootstrap({
      tasks: [
        { task_id: "task-icml", title: "ICML roommate", task_type: "conference_room_share", goal: "Find a roommate", status: "SEARCHING", conversation_id: "conversation-icml", intent_id: "intent-icml" },
        { task_id: "task-dinner", title: "Seoul dinner", task_type: "conference_dinner", goal: "Find dinner", status: "SEARCHING", conversation_id: "conversation-dinner", intent_id: "intent-dinner" },
      ],
      conversationMessages: [
        { message_id: "m1", conversation_id: "conversation-icml", task_id: "task-icml", role: "PERSONAL_AGENT", author_id: "qi-agent", content: "I am evaluating Maya and Lena." },
        { message_id: "m2", conversation_id: "conversation-dinner", task_id: "task-dinner", role: "PERSONAL_AGENT", author_id: "qi-agent", content: "I found a dinner group." },
      ],
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => data }));
    render(<App />);
    const conversation = await screen.findByRole("textbox", { name: "Message Qi Agent · task conversation" });
    const panel = conversation.closest(".conversation-panel");
    expect(panel).not.toBeNull();
    expect(within(panel as HTMLElement).getByText("I am evaluating Maya and Lena.")).toBeInTheDocument();
    expect(within(panel as HTMLElement).queryByText("I found a dinner group.")).not.toBeInTheDocument();
  });

  it("publishes an approved draft and immediately starts the live agent workflow", async () => {
    window.history.replaceState({}, "", "/requests/task-icml");
    const task = { task_id: "task-icml", title: "ICML roommate", task_type: "conference_room_share", goal: "Find a roommate", status: "DRAFT", conversation_id: "conversation-icml", intent_id: "intent-icml" };
    const draft = { intent_id: "intent-icml", owner_agent_id: "qi-agent", public_title: "Looking for an ICML roommate", public_summary: "Share a quiet room in Seoul.", public_constraints: { event: "ICML", location: "Seoul", date_start: "2026-07-06", date_end: "2026-07-10", roommate_gender_preference: "female" }, public_requirements: ["ICML attendee"], status: "DRAFT", version: 1 };
    const data = bootstrap({ tasks: [task], demoState: { ...bootstrap().demoState, activeIntent: draft, intentRegistry: [draft] } });
    const review = { publicPost: draft, agentOnly: { quiet_overnight_compatibility: { importance: "high", source: "explicit_user_input" }, maximum_additional_cost_usd: 70, partial_date_overlap_allowed: true }, protected: { count: 1, summary: "Protected fact", disclosure: "Never included in public posts or peer-agent messages" }, fieldProvenance: {}, uncertainties: [] };
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const requestPath = String(input);
      if (requestPath === "/api/os/bootstrap") return { ok: true, json: async () => data };
      if (requestPath === "/api/intents/intent-icml/review") return { ok: true, json: async () => review };
      if (requestPath === "/api/intents/publish") return { ok: true, json: async () => ({ intent: { ...draft, status: "OPEN" } }) };
      throw new Error(`Unexpected request: ${requestPath}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    class MockEventSource {
      static latestUrl = "";
      onerror: (() => void) | null = null;
      constructor(url: string | URL) { MockEventSource.latestUrl = String(url); }
      addEventListener() {}
      close() {}
    }
    vi.stubGlobal("EventSource", MockEventSource);
    render(<App />);
    expect(await screen.findByText("Review what Qi will publish")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve post & publish" }));
    await waitFor(() => expect(MockEventSource.latestUrl).toBe("/api/demo/run/stream?intent_id=intent-icml"));
  });

  it("requires an expired capacity hold to be revalidated before exact approval", async () => {
    window.history.replaceState({}, "", "/requests/task-icml");
    const task = { task_id: "task-icml", title: "ICML roommate", task_type: "conference_room_share", goal: "Find a roommate", status: "NEEDS_DECISION", conversation_id: "conversation-icml", intent_id: "intent-icml" };
    const data = bootstrap({
      tasks: [task],
      decisions: [{ decision_id: "decision-1", task_id: "task-icml", type: "APPROVE_PROPOSAL", status: "OPEN", title: "Maya's Agent accepted a proposal", summary: "Review the exact effect.", authoritative_entity_ids: ["proposal-1"], expires_at: "2020-01-01T00:00:00Z" }],
      demoState: {
        ...bootstrap().demoState,
        run: { runId: "run-1", status: "WAITING_FOR_HUMAN_APPROVAL" },
        approvalRequests: [{ runId: "run-1", proposalId: "proposal-1", proposalVersion: 1, candidateIdentitySummary: "Maya", sharedDates: { start: "2026-07-06", end: "2026-07-09" }, costDifferenceUsd: 62, delegatedMaximumUsd: 70, holdExpiresAt: "2020-01-01T00:00:00Z" }],
      },
    });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(await screen.findByText("HOLD EXPIRED")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve exact effect" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revalidate offer" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/demo/revalidate", expect.objectContaining({ method: "POST" })));
  });
});
