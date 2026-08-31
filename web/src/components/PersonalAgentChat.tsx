import { Bot, Check, ChevronRight, FileText, MemoryStick, MessageSquareMore, RotateCcw, Send, ShieldCheck, Square, UserRound, UsersRound, Wrench, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../auth";

type Item = Record<string, unknown>;

interface StreamEvent {
  type: string;
  invocation_id?: string;
  delta?: string;
  tool_call_id?: string;
  tool_name?: string;
  error?: string;
  message?: Item;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function number(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function timestamp(value: unknown): string {
  if (typeof value !== "string") return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function readEventStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.body) throw new Error("The Agent stream did not open.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    if (done && buffer.trim()) {
      frames.push(buffer);
      buffer = "";
    }
    for (const frame of frames) {
      if (!frame.trim() || frame.startsWith(":")) continue;
      const eventName = frame.split("\n").find((line) => line.startsWith("event:"))?.slice(6).trim();
      const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
      if (!eventName || !data) continue;
      onEvent({ ...JSON.parse(data) as StreamEvent, type: eventName });
    }
    if (done) break;
  }
}

export function PersonalAgentChat({
  conversation,
  messages,
  taskId,
  refresh,
  title = "My Personal Agent",
  directives = [],
  tasks = [],
  posts = [],
  decisions = [],
  rooms = [],
  memories = [],
  navigate,
}: {
  conversation?: Item;
  messages: Item[];
  taskId?: string;
  refresh: () => Promise<void>;
  title?: string;
  directives?: Item[];
  tasks?: Item[];
  posts?: Item[];
  decisions?: Item[];
  rooms?: Item[];
  memories?: Item[];
  navigate?: (path: string) => void;
}) {
  const { request, streamRequest } = useAuth();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [partial, setPartial] = useState("");
  const [optimistic, setOptimistic] = useState<Item | null>(null);
  const [tools, setTools] = useState<{ id: string; name: string; done: boolean }[]>([]);
  const [failure, setFailure] = useState("");
  const [invocationId, setInvocationId] = useState("");
  const [lastTurn, setLastTurn] = useState<{ content: string; clientId: string } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const conversationId = text(conversation?.conversation_id);
  const visibleMessages = useMemo(() => {
    const current = [...messages].sort((a, b) => text(a.created_at).localeCompare(text(b.created_at)));
    if (optimistic && !current.some((item) => item.client_message_id === optimistic.client_message_id)) current.push(optimistic);
    return current;
  }, [messages, optimistic]);
  const latestLive = [...messages].reverse().find((message) => message.role === "PERSONAL_AGENT" && message.message_classification === "FRESH_LIVE_GEMINI_RESPONSE");
  const conversationDirectives = useMemo(
    () => directives.filter((item) => item.conversation_id === conversationId).sort((a, b) => text(a.created_at).localeCompare(text(b.created_at))),
    [conversationId, directives],
  );
  const referencedDirectiveIds = useMemo(
    () => new Set(messages.flatMap((message) => Array.isArray(message.presentation_directive_ids) ? message.presentation_directive_ids.map(String) : [])),
    [messages],
  );
  const unlinkedDirectives = conversationDirectives.filter((item) => !referencedDirectiveIds.has(text(item.directive_id))).slice(-4);

  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [visibleMessages, partial, tools]);
  useEffect(() => { textarea.current?.focus(); }, [conversationId]);

  async function send(content: string, retryOf?: string) {
    const clean = content.trim();
    if (!conversationId || clean.length < 1 || busy) return;
    const clientId = crypto.randomUUID();
    setBusy(true);
    setFailure("");
    setPartial("");
    setTools([]);
    setInvocationId("");
    setOptimistic({
      message_id: `optimistic-${clientId}`,
      client_message_id: clientId,
      conversation_id: conversationId,
      role: "USER",
      content: clean,
      created_at: new Date().toISOString(),
    });
    setLastTurn({ content: clean, clientId });
    setDraft("");
    try {
      const response = await streamRequest(`/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content: clean,
          client_message_id: clientId,
          task_id: taskId || null,
          retry_of: retryOf || null,
        }),
      });
      setInvocationId(response.headers.get("X-PairPilot-Invocation-Id") || "");
      await readEventStream(response, (event) => {
        if (event.invocation_id) setInvocationId(event.invocation_id);
        if (event.type === "agent.text.delta") setPartial((current) => current + text(event.delta));
        if (event.type === "tool.started") setTools((current) => [...current, { id: text(event.tool_call_id), name: text(event.tool_name), done: false }]);
        if (event.type === "tool.completed") setTools((current) => current.map((tool) => tool.id === event.tool_call_id ? { ...tool, done: true } : tool));
        if (event.type === "agent.error") setFailure(text(event.error) || "The live Agent turn failed.");
      });
      await refresh();
    } catch (reason) {
      setFailure(reason instanceof Error ? reason.message : "The live Agent turn failed.");
    } finally {
      setBusy(false);
      setPartial("");
      setTools([]);
      setOptimistic(null);
    }
  }

  async function stop() {
    if (!invocationId) return;
    await request(`/api/v1/invocations/${encodeURIComponent(invocationId)}/stop`, { method: "POST", body: "{}" });
  }

  async function publishDraft(task: Item) {
    const taskIdForCard = text(task.task_id);
    const draft = (task.agent_public_draft || {}) as Item;
    const requirements = Array.isArray(draft.public_requirements) ? draft.public_requirements.map(String) : [];
    setFailure("");
    try {
      await request(`/api/app/tasks/${encodeURIComponent(taskIdForCard)}/publish`, {
        method: "POST",
        body: JSON.stringify({
          public_title: text(draft.public_title) || text(task.title),
          public_summary: text(draft.public_summary) || text(task.goal),
          public_requirements: requirements,
        }),
      });
      await refresh();
    } catch (reason) {
      setFailure(reason instanceof Error ? reason.message : "Could not publish this post.");
    }
  }

  function directiveCard(directive: Item) {
    const action = text(directive.action);
    const entityIds = Array.isArray(directive.entity_ids) ? directive.entity_ids.map(String) : [];
    const directiveTaskId = text(directive.task_id) || entityIds.find((id) => id.startsWith("task_")) || "";
    const task = tasks.find((item) => item.task_id === directiveTaskId || entityIds.includes(text(item.intent_id)));
    const post = posts.find((item) => entityIds.includes(text(item.intent_id)) || item.task_id === directiveTaskId);
    const decision = decisions.find((item) => entityIds.includes(text(item.decision_id)) || item.task_id === directiveTaskId);
    const room = rooms.find((item) => entityIds.includes(text(item.room_id)));
    const memory = memories.find((item) => entityIds.includes(text(item.memory_id)));
    const key = text(directive.directive_id);
    if (action === "SHOW_POST") {
      const draft = (task?.agent_public_draft || {}) as Item;
      const published = Boolean(post);
      return <article className="agent-inline-card post" key={key}>
        <header><FileText size={17} /><span>{published ? "Published post" : "Post ready for review"}</span><b>{published ? text(post?.status) : "DRAFT"}</b></header>
        <h3>{text(post?.public_title) || text(draft.public_title) || text(task?.title) || "Public post draft"}</h3>
        <p>{text(post?.public_summary) || text(draft.public_summary) || text(task?.goal) || text(directive.explanation)}</p>
        <footer>{!published && task ? <button className="inline-primary" onClick={() => void publishDraft(task)}><Check size={14} /> Approve & publish</button> : null}<button onClick={() => directiveTaskId && navigate?.(`/app/requests/${directiveTaskId}`)}>Open details <ChevronRight size={14} /></button></footer>
      </article>;
    }
    if (action === "SHOW_ROOM" && room) return <button className="agent-inline-card clickable" key={key} onClick={() => navigate?.(`/app/rooms/${text(room.room_id)}`)}><MessageSquareMore size={18} /><span><b>Agent coordination room</b><small>{text(room.status)} · open conversation</small></span><ChevronRight size={16} /></button>;
    if (action === "SHOW_MEMORY" && memory) return <button className="agent-inline-card clickable" key={key} onClick={() => navigate?.("/app/memory")}><MemoryStick size={18} /><span><b>{text(memory.title) || "Memory for review"}</b><small>{text(memory.content)}</small></span><ChevronRight size={16} /></button>;
    if (action === "SHOW_CANDIDATE_COMPARISON") return <button className="agent-inline-card clickable" key={key} onClick={() => directiveTaskId && navigate?.(`/app/requests/${directiveTaskId}`)}><UsersRound size={18} /><span><b>Candidate ranking updated</b><small>{text(directive.explanation)}</small></span><ChevronRight size={16} /></button>;
    if (action === "SHOW_DECISION" && decision) return <button className="agent-inline-card clickable" key={key} onClick={() => directiveTaskId && navigate?.(`/app/requests/${directiveTaskId}`)}><Check size={18} /><span><b>{text(decision.title) || "Decision needed"}</b><small>{text(decision.summary)}</small></span><ChevronRight size={16} /></button>;
    if (task) return <button className="agent-inline-card clickable" key={key} onClick={() => navigate?.(`/app/requests/${text(task.task_id)}`)}><FileText size={18} /><span><b>{text(task.title)}</b><small>{text(task.status)} · {text(task.goal)}</small></span><ChevronRight size={16} /></button>;
    return <article className="agent-inline-card" key={key}><X size={17} /><span><b>Update</b><small>{text(directive.explanation)}</small></span></article>;
  }

  return <section className="real-agent-chat">
    <header className="real-chat-header">
      <span className="agent-avatar"><Bot size={19} /></span>
      <div><h2>{title}</h2><p>{taskId ? "Private task context" : "Private global context · persistent session"}</p></div>
      <span className={latestLive ? "live-model-badge" : "ready-model-badge"}><i /> {latestLive ? `${text(latestLive.model_id) || "Gemini"} · live` : "Ready"}</span>
    </header>
    <div className="real-message-list" aria-live="polite">
      {!visibleMessages.length && !busy ? <div className="real-chat-welcome"><Bot size={32} /><h1>Tell me what you need.</h1><p>Use normal language. I can ask follow-up questions, create a private request, draft a post, search compatible posts, and coordinate with multiple agents—while keeping publishing and commitments under your control.</p></div> : null}
      {visibleMessages.map((message) => {
        const fromUser = message.role === "USER";
        const toolCount = Array.isArray(message.tool_call_ids) ? message.tool_call_ids.length : 0;
        return <article className={`real-chat-message ${fromUser ? "user" : "agent"}`} key={text(message.message_id)}>
          <span>{fromUser ? <UserRound size={15} /> : <Bot size={15} />}</span>
          <div><header><strong>{fromUser ? "You" : "Personal Agent"}</strong><time>{timestamp(message.created_at || message.completed_at)}</time></header><p>{text(message.content)}</p>{Array.isArray(message.presentation_directive_ids) ? message.presentation_directive_ids.map(String).map((id) => conversationDirectives.find((item) => item.directive_id === id)).filter(Boolean).map((item) => directiveCard(item as Item)) : null}{!fromUser ? <details className="message-provenance"><summary>Response audit</summary><dl><dt>Source</dt><dd>{message.message_classification === "FRESH_LIVE_GEMINI_RESPONSE" ? "Fresh live model response" : text(message.message_classification) || "Recorded message"}</dd><dt>Model</dt><dd>{text(message.model_id) || "Not recorded"}</dd><dt>Invocation</dt><dd>{text(message.adk_invocation_id) || "Not recorded"}</dd><dt>Latency</dt><dd>{number(message.latency_ms) !== undefined ? `${number(message.latency_ms)} ms` : "Not recorded"}</dd><dt>Tokens</dt><dd>{number(message.input_token_count) ?? "?"} in · {number(message.output_token_count) ?? "?"} out</dd><dt>Tools</dt><dd>{toolCount}</dd></dl></details> : null}</div>
        </article>;
      })}
      {unlinkedDirectives.map((item) => directiveCard(item))}
      {(partial || busy) && !failure ? <article className="real-chat-message agent streaming"><span><Bot size={15} /></span><div><header><strong>Personal Agent</strong><small>working live</small></header>{partial ? <p>{partial}</p> : <p className="thinking"><i /><i /><i /></p>}{tools.length ? <div className="tool-progress">{tools.map((tool) => <span key={tool.id}><Wrench size={12} /> {tool.name.replaceAll("_", " ")} · {tool.done ? "done" : "running"}</span>)}</div> : null}</div></article> : null}
      {failure ? <article className="agent-failure"><strong>Agent turn failed</strong><p>{failure}</p><span>No assistant answer was fabricated or saved.</span>{lastTurn ? <button onClick={() => void send(lastTurn.content, lastTurn.clientId)} disabled={busy}><RotateCcw size={14} /> Retry as a new turn</button> : null}</article> : null}
      <div ref={bottom} />
    </div>
    <div className="real-chat-composer"><textarea ref={textarea} aria-label={`Message ${title}`} rows={3} value={draft} disabled={!conversationId} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(draft); } }} placeholder={conversationId ? "Describe the outcome, ask a question, or change a boundary…" : "Preparing your persistent conversation…"} /><footer><span><ShieldCheck size={13} /> Private to your account · Enter to send · Shift+Enter for a new line</span>{busy ? <button className="stop-agent-button" onClick={() => void stop()} disabled={!invocationId}><Square size={13} /> Stop</button> : <button className="send-agent-button" onClick={() => void send(draft)} disabled={!conversationId || !draft.trim()}><Send size={16} /> Send</button>}</footer></div>
  </section>;
}
