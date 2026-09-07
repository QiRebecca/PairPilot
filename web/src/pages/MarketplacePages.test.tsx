import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MarketplaceExplorePage } from "./MarketplacePages";

const authMocks = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("../auth", () => ({ useAuth: () => authMocks }));

const task = {
  task_id: "task_one",
  task_type: "COFFEE_CHAT",
  status: "ACTIVE",
  title: "Find an agent systems coffee chat",
};

const post = {
  intent_id: "intent_peer",
  task_type: "COFFEE_CHAT",
  status: "OPEN",
  public_display_name: "Nora Chen",
  public_title: "Coffee chat about multi-agent systems",
  public_summary:
    "Looking for a practical exchange about agent interoperability.",
  public_constraints: {
    location: "London",
    date_start: "2026-09-12",
    date_end: "2026-09-12",
  },
  public_requirements: ["A2A", "hands-on builders"],
  capacity_remaining: 1,
  related_task_id: "task_one",
  surfaced_reasons: ["Compatible request type"],
  saved: false,
  updated_at: new Date().toISOString(),
};

describe("Explore social intent feed", () => {
  beforeEach(() => {
    authMocks.request.mockReset();
    authMocks.request.mockImplementation((path: string) => {
      if (path === "/api/app/explore/search") {
        return Promise.resolve({
          items: [post],
          count: 1,
          view: "FOR_YOUR_REQUESTS",
          retrieval: {
            structured_filters: true,
            semantic_vector: false,
            text_relevance: true,
            note: "test",
          },
        });
      }
      if (path.includes("/candidates/") && path.endsWith("/contact")) {
        return Promise.resolve({
          status: "CONTACTED",
          result: { contacted: 1, failures: [] },
        });
      }
      return Promise.resolve({});
    });
  });

  it("shows identity, context and direct Agent actions in one feed card", async () => {
    render(
      <MarketplaceExplorePage
        tasks={[task]}
        myPosts={[{ task_id: "task_one", status: "OPEN" }]}
        communities={[
          { community_id: "community_one", name: "AI Builders London" },
        ]}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByText("Coffee chat about multi-agent systems"),
    ).toBeInTheDocument();
    expect(screen.getByText("Nora Chen")).toBeInTheDocument();
    expect(screen.getByText("London")).toBeInTheDocument();
    expect(
      screen.getByText("Why your Agent surfaced this"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ask my Agent" }));
    await waitFor(() =>
      expect(authMocks.request).toHaveBeenCalledWith(
        "/api/app/tasks/task_one/candidates/intent_peer/contact",
        { method: "POST", body: "{}" },
      ),
    );
    expect(
      await screen.findByText(
        /opened a conversation with the other Personal Agent/i,
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(authMocks.request).toHaveBeenCalledWith(
        "/api/app/posts/intent_peer/saved",
        expect.objectContaining({ method: "PUT" }),
      ),
    );
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Saved" })).toHaveLength(2),
    );
  });

  it("does not claim Agent contact when the server found no compatible Post", async () => {
    authMocks.request.mockImplementation((path: string) => {
      if (path === "/api/app/explore/search") {
        return Promise.resolve({
          items: [post],
          count: 1,
          view: "FOR_YOUR_REQUESTS",
          retrieval: {},
        });
      }
      if (path.includes("/candidates/") && path.endsWith("/contact")) {
        return Promise.resolve({
          status: "NO_COMPATIBLE_POST_YET",
          result: { contacted: 0, failures: [] },
        });
      }
      return Promise.resolve({});
    });
    render(
      <MarketplaceExplorePage
        tasks={[task]}
        myPosts={[{ task_id: "task_one", status: "OPEN" }]}
        communities={[]}
        navigate={vi.fn()}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Ask my Agent" }),
    );

    expect(
      await screen.findByText(/not compatible with this Request yet/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        /opened a conversation with the other Personal Agent/i,
      ),
    ).not.toBeInTheDocument();
  });
});
