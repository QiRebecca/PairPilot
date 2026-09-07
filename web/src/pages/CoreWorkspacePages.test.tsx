import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectionsPage } from "./ConnectionPages";
import { MatchesPage } from "./MatchPages";
import { MemoryPage } from "./MemoryPages";

const authMocks = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("../auth", () => ({ useAuth: () => authMocks }));

describe("launch-ready core workspace pages", () => {
  beforeEach(() => authMocks.request.mockReset());

  it("turns an empty Matches workspace into a clear Agent workflow", async () => {
    authMocks.request.mockResolvedValue({
      matches: [],
      sections: {
        NEEDS_ACTION: [],
        UPCOMING: [],
        IN_PROGRESS: [],
        COMPLETED: [],
        CANCELLED: [],
      },
      count: 0,
    });
    const navigate = vi.fn();

    render(<MatchesPage navigate={navigate} />);

    expect(await screen.findByText("No confirmed Match yet")).toBeInTheDocument();
    expect(screen.getByLabelText("Match summary")).toHaveTextContent(
      "Needs Action",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Tell my Agent what I need" }),
    );
    expect(navigate).toHaveBeenCalledWith("/app/agent");
  });

  it("explains how Connections are earned and links back to discovery", async () => {
    authMocks.request.mockResolvedValue({
      connections: [],
      views: {
        ALL: [],
        TRUSTED: [],
        RECENT: [],
        INTRODUCERS: [],
        COMMUNITIES: [],
        NEEDS_REVIEW: [],
        BLOCKED: [],
      },
      count: 0,
      graph: { nodes: [], edges: [] },
    });
    const navigate = vi.fn();

    render(<ConnectionsPage navigate={navigate} />);

    expect(
      await screen.findByText("Your Connections will grow from real plans"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Connection summary")).toHaveTextContent(
      "Needs review",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Find people and Agents" }),
    );
    expect(navigate).toHaveBeenCalledWith("/app/explore");
  });

  it("keeps empty Memory private, explicit and actionable", async () => {
    authMocks.request.mockResolvedValue({
      memories: [],
      groups: {
        ABOUT_ME: [],
        PREFERENCES: [],
        BOUNDARIES: [],
        ROUTINES: [],
        COMMUNICATION: [],
        TASK_SPECIFIC: [],
        RELATIONSHIPS: [],
        WAITING_FOR_CONFIRMATION: [],
        RECENTLY_USED: [],
        ARCHIVED: [],
      },
      count: 0,
    });
    const navigate = vi.fn();

    render(<MemoryPage navigate={navigate} />);

    expect(await screen.findByText("No retained Memory")).toBeInTheDocument();
    expect(
      screen.getByText(/nothing becomes reusable until you confirm it/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Talk to my Agent" }));
    expect(navigate).toHaveBeenCalledWith("/app/agent");
  });
});
