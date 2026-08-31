import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PersonalAgentChat } from "./PersonalAgentChat";

const authMocks = vi.hoisted(() => ({
  request: vi.fn(),
  streamRequest: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => authMocks,
}));

describe("PersonalAgentChat", () => {
  beforeEach(() => {
    authMocks.request.mockReset();
    authMocks.streamRequest.mockReset();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("shows an honest model error and never invents an assistant answer", async () => {
    const stream = [
      "event: message.accepted",
      'data: {"type":"message.accepted","invocation_id":"invocation-test"}',
      "",
      "event: agent.error",
      'data: {"type":"agent.error","invocation_id":"invocation-test","error":"The live Personal Agent turn failed. Retry when ready."}',
      "",
    ].join("\n");
    authMocks.streamRequest.mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(
      <PersonalAgentChat
        conversation={{ conversation_id: "user:uid-a:global" }}
        messages={[]}
        refresh={refresh}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Message My Personal Agent" }), {
      target: { value: "Please run a real turn." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Agent turn failed")).toBeInTheDocument();
    expect(
      screen.getByText("No assistant answer was fabricated or saved."),
    ).toBeInTheDocument();
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    expect(screen.queryByText("A convenient fallback answer")).not.toBeInTheDocument();
  });
});
