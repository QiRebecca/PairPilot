import { Bot, CheckCircle2, CircleAlert, Clock3, LockKeyhole, MessageSquareMore, Send, UsersRound, VolumeX, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { PersonalAgentChat } from "../components/PersonalAgentChat";

type RecordValue = Record<string, unknown>;
type Channel = "PRIVATE_USER_AGENT" | "AGENTS_ONLY" | "SHARED_ROOM";

interface RoomListPayload {
  rooms: RecordValue[];
  sections: Record<string, RecordValue[]>;
  count: number;
}

interface RoomWorkspacePayload {
  room: RecordValue;
  summary: {
    agreed: RecordValue[];
    unresolved: unknown[];
    conflicts: unknown[];
    uncertainties: unknown[];
    current_proposal: RecordValue | null;
    hold_status: string;
    next_action: string;
  };
  channels: Record<Channel, RecordValue[]>;
  channel_permissions: Record<Channel, { read: boolean; write: boolean; policy_redacted?: boolean }>;
}

interface RoomChatData {
  tasks: RecordValue[];
  conversations: RecordValue[];
  conversationMessages: RecordValue[];
  presentationDirectives: RecordValue[];
  myPosts: RecordValue[];
  decisions: RecordValue[];
  rooms: RecordValue[];
  matches: RecordValue[];
  relationships: RecordValue[];
  communities: RecordValue[];
  memories: RecordValue[];
}

const asString = (value: unknown) => typeof value === "string" ? value : "";
const sectionLabels: Record<string, string> = {
  NEEDS_YOUR_INPUT: "Needs Your Input",
  AGENT_NEGOTIATING: "Agent Negotiating",
  WAITING_FOR_PEER: "Waiting for Peer",
  PROPOSAL_READY: "Proposal Ready",
  SHARED_ROOMS: "Shared Rooms",
  CLOSED: "Closed",
};
const channelLabels: Record<Channel, string> = {
  PRIVATE_USER_AGENT: "Private with My Agent",
  AGENTS_ONLY: "Agents-only negotiation",
  SHARED_ROOM: "Shared Human-Agent Room",
};

export function RoomsPage({ navigate }: { navigate: (path: string) => void }) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<RoomListPayload | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void request<RoomListPayload>("/api/app/rooms").then(setPayload).catch((reason: Error) => setError(reason.message)); }, [request]);
  return <div className="beta-page"><header className="page-title"><span className="eyebrow">PARTICIPANT-SCOPED WORKSPACES</span><h1>Rooms</h1><p>Your Personal Agent negotiates in a private Agent channel. Direct human coordination unlocks only after the required consent boundary.</p></header>{error ? <div className="form-error">{error}</div> : null}{!payload ? <div className="community-loading">Loading Rooms…</div> : payload.count === 0 ? <div className="empty-state"><MessageSquareMore /><h3>No Rooms yet</h3><p>A Room appears when two compatible Personal Agents begin a bounded negotiation.</p></div> : <div className="room-section-list">{Object.entries(sectionLabels).map(([section, label]) => { const rooms = payload.sections[section] || []; return rooms.length ? <section key={section}><div className="section-heading"><h2>{label}</h2><span className="status-pill">{rooms.length}</span></div><div className="request-grid">{rooms.map((room) => <button className="request-card room-list-card" key={asString(room.room_id)} onClick={() => navigate(`/app/rooms/${asString(room.room_id)}`)}><span className="status-pill">{asString(room.state)}</span><h3>{asString(room.room_type).replaceAll("_", " ")}</h3><p>{asString(room.last_material_update) || asString(room.latest_meaningful_event) || (room.human_participation_available ? "Shared human coordination is open." : "Personal Agents are coordinating within your authority.")}</p><span>Open coordination workspace →</span></button>)}</div></section> : null; })}</div>}</div>;
}

export function RoomDetailPage({ roomId, navigate, data, refresh }: { roomId: string; navigate: (path: string) => void; data: RoomChatData; refresh: () => Promise<void> }) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<RoomWorkspacePayload | null>(null);
  const [channel, setChannel] = useState<Channel>("PRIVATE_USER_AGENT");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => { try { setPayload(await request<RoomWorkspacePayload>(`/api/app/rooms/${roomId}`)); setError(""); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load Room."); } }, [request, roomId]);
  useEffect(() => { void load(); }, [load]);
  const messages = useMemo(() => payload?.channels[channel] || [], [channel, payload]);

  async function send(event: FormEvent) {
    event.preventDefault(); const body = content.trim(); if (!body || !payload?.channel_permissions[channel].write) return;
    setBusy(true); setError("");
    try { await request(`/api/app/rooms/${roomId}/channels/${channel}/messages`, { method: "POST", body: JSON.stringify({ content: body, authorship: "HUMAN_WRITTEN", idempotency_key: crypto.randomUUID(), reply_to: null }) }); setContent(""); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Message was not sent."); }
    finally { setBusy(false); }
  }
  async function leave() { setBusy(true); try { await request(`/api/app/rooms/${roomId}/leave`, { method: "POST", body: "{}" }); navigate("/app/rooms"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not leave Room."); setBusy(false); } }
  async function toggleMute() { setBusy(true); try { await request(`/api/app/rooms/${roomId}/muted`, { method: muted ? "DELETE" : "PUT" }); setMuted(!muted); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update Room notifications."); } finally { setBusy(false); } }

  if (!payload) return <div className="beta-page">{error ? <div className="form-error">{error}</div> : <div className="community-loading">Loading coordination workspace…</div>}</div>;
  const room = payload.room;
  const task = (room.associated_request || {}) as RecordValue;
  const candidate = (room.candidate_post || {}) as RecordValue;
  const participants = Array.isArray(room.participants) ? room.participants as RecordValue[] : [];
  const permission = payload.channel_permissions[channel];
  const globalConversation = data.conversations.find((item) => item.kind === "GLOBAL_PERSONAL_AGENT");
  const globalMessages = data.conversationMessages.filter((item) => item.conversation_id === globalConversation?.conversation_id);
  return <div className="beta-page room-workspace"><button className="text-button" onClick={() => navigate("/app/rooms")}>← All Rooms</button><header className="room-workspace-header"><div><span className="eyebrow">{asString(room.room_type).replaceAll("_", " ")}</span><h1>{asString(task.title) || asString(candidate.public_title) || "Coordination Room"}</h1><p>{participants.map((item) => asString(item.display_name)).filter(Boolean).join(" · ")}</p></div><div className="room-header-actions"><button className="secondary-button" disabled={busy} onClick={() => void toggleMute()}><VolumeX size={14} />{muted ? "Unmute" : "Mute"}</button><button className="danger-button" disabled={busy} onClick={() => void leave()}><X size={14} />Leave</button></div></header>{error ? <div className="form-error">{error}</div> : null}<div className="room-facts"><article><small>State</small><strong>{asString(room.state).replaceAll("_", " ")}</strong></article><article><small>Next actor</small><strong>{asString(room.next_expected_actor) || payload.summary.next_action}</strong></article><article><small>Autonomy</small><strong>{asString(room.autonomy_mode)}</strong></article><article><small>Candidate Post</small><strong>{asString(candidate.public_title) || "Not linked"}</strong></article></div><div className="room-workspace-grid"><section className="room-main"><nav className="room-channel-tabs">{(Object.keys(channelLabels) as Channel[]).map((item) => <button key={item} className={channel === item ? "active" : ""} onClick={() => setChannel(item)}>{item === "PRIVATE_USER_AGENT" ? <LockKeyhole size={14} /> : item === "AGENTS_ONLY" ? <Bot size={14} /> : <UsersRound size={14} />}{channelLabels[item]}</button>)}</nav><div className="room-channel-notice">{channel === "PRIVATE_USER_AGENT" ? "This is the same persistent Personal Agent conversation, now scoped to this Request and Room. Nothing is sent to the other side." : channel === "AGENTS_ONLY" ? "You can inspect a policy-redacted transcript. Humans cannot type here." : permission.write ? "Both approved humans and their Personal Agents can coordinate here." : "This channel unlocks only after mutual consent."}</div>{channel === "PRIVATE_USER_AGENT" ? <PersonalAgentChat title="My Personal Agent · private Room context" conversation={globalConversation} messages={globalMessages} taskId={asString(task.task_id)} refresh={async () => { await Promise.all([refresh(), load()]); }} directives={data.presentationDirectives} tasks={data.tasks} posts={data.myPosts} decisions={data.decisions} rooms={data.rooms} matches={data.matches} connections={data.relationships} communities={data.communities} memories={data.memories} navigate={navigate} /> : <><div className="room-thread v2-room-thread">{messages.map((message) => <article className={message.speaker_type === "HUMAN" ? "human" : "agent"} key={asString(message.message_id)}><header><strong>{asString(message.speaker_type).replaceAll("_", " ")}</strong><small>{asString(message.authorship).replaceAll("_", " ")}</small></header><p>{asString(message.content)}</p>{message.policy_redacted ? <span className="redaction-label"><ShieldNotice />Policy-redacted for owner inspection</span> : null}</article>)}{!messages.length ? <div className="empty-state compact"><MessageSquareMore /><h3>No messages in this channel</h3><p>The three channel histories are stored and authorized separately.</p></div> : null}</div><form className="room-channel-composer" onSubmit={send}><textarea value={content} disabled={!permission.write || busy} onChange={(event) => setContent(event.target.value)} placeholder={channel === "SHARED_ROOM" && permission.write ? "Send as myself…" : "You cannot type in this channel"} /><footer><span>{permission.write ? "Shared channel · explicit human authorship" : "Read-only channel"}</span><button className="primary-button" disabled={!permission.write || busy || !content.trim()}><Send size={14} />Send as myself</button></footer></form></>}</section><RoomSummary summary={payload.summary} /></div></div>;
}

function ShieldNotice() { return <CircleAlert size={12} />; }

function RoomSummary({ summary }: { summary: RoomWorkspacePayload["summary"] }) {
  return <aside className="room-summary-panel"><span className="eyebrow">LIVE COORDINATION SUMMARY</span><h2>What is settled</h2>{summary.agreed.length ? <ul className="agreed-list">{summary.agreed.map((item) => <li key={asString(item.field)}><CheckCircle2 size={13} /><span>{asString(item.field).replaceAll("_", " ")}: {String(item.value ?? "")}</span></li>)}</ul> : <p>No agreed terms yet.</p>}<h2>Unresolved</h2>{summary.unresolved.length ? <ul>{summary.unresolved.map((item, index) => <li key={index}>{String(item)}</li>)}</ul> : <p>Nothing explicitly unresolved.</p>}<h2>Conflicts & uncertainties</h2>{[...summary.conflicts, ...summary.uncertainties].length ? <ul>{[...summary.conflicts, ...summary.uncertainties].map((item, index) => <li key={index}>{String(item)}</li>)}</ul> : <p>No recorded conflict.</p>}<div className="next-action-card"><Clock3 size={16} /><span><small>Next action</small><strong>{summary.next_action}</strong></span></div><small>Hold status: {summary.hold_status}</small></aside>;
}
