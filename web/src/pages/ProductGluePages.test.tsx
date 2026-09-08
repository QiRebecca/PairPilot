import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationsPage } from "./ProductGluePages";

const authMocks = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("../auth", () => ({ useAuth: () => authMocks }));

describe("attention state synchronization", () => {
  beforeEach(() => authMocks.request.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("notifies the app shell immediately after marking notifications read", async () => {
    let unread = true;
    authMocks.request.mockImplementation(
      async (path: string, init?: RequestInit) => {
        if (
          path === "/api/app/notifications/read-all" &&
          init?.method === "PUT"
        ) {
          unread = false;
          return {};
        }
        if (path === "/api/app/notifications")
          return {
            notifications: [
              {
                notification_id: "notification-1",
                category: "MATCH_UPDATE",
                status: unread ? "UNREAD" : "READ",
                title: "Match updated",
                body: "The shared Room is ready.",
                entity_route: "/app/matches/match-1",
              },
            ],
            categories: { MATCH_UPDATE: [] },
            unread_count: unread ? 1 : 0,
            settings: {},
          };
        return {};
      },
    );
    const changed = vi.fn();
    window.addEventListener("pairpilot:attention-changed", changed);

    render(<NotificationsPage navigate={vi.fn()} />);
    await screen.findByText("Match updated");
    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Mark all read" }),
      ).toBeDisabled(),
    );
    expect(authMocks.request.mock.calls.map(([path]) => path)).toEqual([
      "/api/app/notifications",
      "/api/app/notifications/read-all",
      "/api/app/notifications",
    ]);
    window.removeEventListener("pairpilot:attention-changed", changed);
  });
});
