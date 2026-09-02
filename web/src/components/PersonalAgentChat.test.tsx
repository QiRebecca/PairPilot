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

  it("allows two consecutive turns in the same persistent global conversation", async () => {
    const completedStream = () => [
      "event: message.accepted",
      'data: {"type":"message.accepted","invocation_id":"invocation-test"}',
      "",
      "event: agent.text.delta",
      'data: {"type":"agent.text.delta","invocation_id":"invocation-test","delta":"Understood."}',
      "",
      "event: agent.completed",
      'data: {"type":"agent.completed","invocation_id":"invocation-test","message":{"content":"Understood."}}',
      "",
    ].join("\n");
    authMocks.streamRequest
      .mockResolvedValueOnce(new Response(completedStream(), { status: 200 }))
      .mockResolvedValueOnce(new Response(completedStream(), { status: 200 }));
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(
      <PersonalAgentChat
        conversation={{ conversation_id: "user:uid-a:global", task_id: null }}
        messages={[]}
        refresh={refresh}
      />,
    );
    const textbox = screen.getByRole("textbox", {
      name: "Message My Personal Agent",
    });

    fireEvent.change(textbox, { target: { value: "First turn" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(authMocks.streamRequest).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeDisabled());

    fireEvent.change(textbox, { target: { value: "Second turn" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(authMocks.streamRequest).toHaveBeenCalledTimes(2));

    const firstBody = JSON.parse(
      String(authMocks.streamRequest.mock.calls[0][1]?.body),
    ) as { client_message_id: string; content: string; task_id: string | null };
    const secondBody = JSON.parse(
      String(authMocks.streamRequest.mock.calls[1][1]?.body),
    ) as { client_message_id: string; content: string; task_id: string | null };
    expect(firstBody).toMatchObject({ content: "First turn", task_id: null });
    expect(secondBody).toMatchObject({ content: "Second turn", task_id: null });
    expect(secondBody.client_message_id).not.toBe(firstBody.client_message_id);
  });

  it("replays durable events after a stream disconnects", async () => {
    const interrupted = [
      "id: 1",
      "event: message.accepted",
      'data: {"type":"message.accepted","invocation_id":"invocation-replay"}',
      "",
    ].join("\n");
    const replayed = [
      "id: 2",
      "event: agent.completed",
      'data: {"type":"agent.completed","invocation_id":"invocation-replay","message":{"content":"Recovered."}}',
      "",
    ].join("\n");
    authMocks.streamRequest
      .mockResolvedValueOnce(
        new Response(interrupted, {
          status: 200,
          headers: { "X-PairPilot-Invocation-Id": "invocation-replay" },
        }),
      )
      .mockResolvedValueOnce(new Response(replayed, { status: 200 }));
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(
      <PersonalAgentChat
        conversation={{ conversation_id: "user:uid-a:global" }}
        messages={[]}
        refresh={refresh}
      />,
    );
    fireEvent.change(
      screen.getByRole("textbox", { name: "Message My Personal Agent" }),
      { target: { value: "Resume this turn safely." } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(authMocks.streamRequest).toHaveBeenCalledTimes(2));
    expect(String(authMocks.streamRequest.mock.calls[1][0])).toContain(
      "/events?invocation_id=invocation-replay&after=1",
    );
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  });

  it("renders an Agent directive as a real clickable task card", () => {
    const navigate = vi.fn();
    render(
      <PersonalAgentChat
        conversation={{ conversation_id: "user:uid-a:global" }}
        messages={[{
          message_id: "assistant-1",
          conversation_id: "user:uid-a:global",
          role: "PERSONAL_AGENT",
          content: "I created the request.",
          presentation_directive_ids: ["directive-1"],
        }]}
        directives={[{
          directive_id: "directive-1",
          conversation_id: "user:uid-a:global",
          task_id: "task-disney",
          action: "OPEN_TASK",
          entity_ids: ["task-disney"],
        }]}
        tasks={[{
          task_id: "task-disney",
          title: "Hong Kong Disneyland buddy",
          goal: "Find someone who enjoys taking photos.",
          status: "DRAFT",
        }]}
        refresh={vi.fn().mockResolvedValue(undefined)}
        navigate={navigate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Hong Kong Disneyland buddy/i }));
    expect(navigate).toHaveBeenCalledWith("/app/requests/task-disney");
  });
});
