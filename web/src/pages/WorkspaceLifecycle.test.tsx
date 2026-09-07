import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RequestWorkspaceV2Page } from "./RequestWorkspaceV2Page";
import { RoomDetailPage } from "./RoomPages";

const authMocks = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("../auth", () => ({ useAuth: () => authMocks }));
vi.mock("../components/PersonalAgentChat", () => ({
  PersonalAgentChat: ({ taskId }: { taskId?: string }) => (
    <div>Persistent Personal Agent · scoped task {taskId || "global"}</div>
  ),
}));

const workspaceData = {
  tasks: [
    {
      task_id: "task_one",
      title: "Find an event teammate",
      goal: "Coordinate a reliable teammate for the event.",
      status: "ACTIVE",
      community_id: "community_one",
      updated_at: "2026-09-01T10:00:00Z",
    },
  ],
  conversations: [
    { conversation_id: "user:owner:global", kind: "GLOBAL_PERSONAL_AGENT" },
  ],
  conversationMessages: [],
  presentationDirectives: [],
  decisions: [],
  rooms: [],
  matches: [],
  myPosts: [],
  relationships: [],
  memories: [],
  communities: [],
  notifications: [],
  candidateAssessments: [],
  candidateRankEvents: [],
};

describe("Startup V2 integrated workspaces", () => {
  beforeEach(() => authMocks.request.mockReset());

  it("keeps Conversation as default and exposes all seven Request tabs", () => {
    render(
      <RequestWorkspaceV2Page
        taskId="task_one"
        data={workspaceData}
        refresh={vi.fn().mockResolvedValue(undefined)}
        navigate={vi.fn()}
      />,
    );
    expect(
      screen.getByText("Persistent Personal Agent · scoped task task_one"),
    ).toBeInTheDocument();
    for (const name of [
      "Conversation",
      "Overview",
      "Post",
      "Candidates",
      "Agent Rooms",
      "Activity",
      "Audit",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(screen.getByText("Background monitoring")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Audit" }));
    expect(screen.getByText("Authoritative object history")).toBeInTheDocument();
  });

  it("uses the same live Personal Agent inside the private Room channel", async () => {
    authMocks.request.mockResolvedValue({
      room: {
        room_id: "room_one",
        room_type: "AGENT_NEGOTIATION",
        state: "AGENT_NEGOTIATION",
        autonomy_mode: "COPILOT",
        participants: [{ display_name: "Owner" }, { display_name: "Peer" }],
        associated_request: { task_id: "task_one", title: "Find an event teammate" },
        candidate_post: { public_title: "Looking for an event teammate" },
      },
      summary: {
        agreed: [],
        unresolved: [],
        conflicts: [],
        uncertainties: [],
        current_proposal: null,
        hold_status: "NONE",
        next_action: "Waiting for the Personal Agents",
      },
      channels: {
        PRIVATE_USER_AGENT: [],
        AGENTS_ONLY: [],
        SHARED_ROOM: [],
      },
      channel_permissions: {
        PRIVATE_USER_AGENT: { read: true, write: true },
        AGENTS_ONLY: { read: true, write: false, policy_redacted: true },
        SHARED_ROOM: { read: false, write: false },
      },
    });
    render(
      <RoomDetailPage
        roomId="room_one"
        navigate={vi.fn()}
        data={workspaceData}
        refresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByText("Persistent Personal Agent · scoped task task_one"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/same persistent Personal Agent conversation/i),
    ).toBeInTheDocument();
  });

  it("closes a Request from its workspace and returns to the Agent", async () => {
    authMocks.request.mockResolvedValue({ status: "CANCELLED" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const refresh = vi.fn().mockResolvedValue(undefined);
    const navigate = vi.fn();
    render(
      <RequestWorkspaceV2Page
        taskId="task_one"
        data={workspaceData}
        refresh={refresh}
        navigate={navigate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close Request" }));

    await waitFor(() =>
      expect(authMocks.request).toHaveBeenCalledWith(
        "/api/app/tasks/task_one/close",
        { method: "POST", body: "{}" },
      ),
    );
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/app/agent"));
  });
});
