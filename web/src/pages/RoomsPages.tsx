import { ArrowRight, Bot, Eye, LockKeyhole, MessageCircle, Send, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import { useState } from "react";
import type { CoordinationRoom, OSBootstrap } from "../types";
import { EmptyState, PageHeading, StatusPill } from "../components/ProductComponents";
import { formatAgent } from "../utils";

function RoomCard({ room, taskTitle, onOpen }: { room: CoordinationRoom; taskTitle: string; onOpen: () => void }) {
  const peer = room.participant_agent_ids.find((id) => id !== "qi-agent") || "Peer Agent";
  return <button className="room-card" onClick={onOpen}><header><span className="room-avatar"><Bot size={17} /></span><div><strong>{formatAgent(peer)}</strong><small>{taskTitle}</small></div><StatusPill status={room.status} /></header><p>{room.latest_meaningful_event}</p><footer><span>{room.room_type.replaceAll("_", " ")}</span><span>{room.human_participation_available ? "Human participation available" : "Agents only"}</span><ArrowRight size={14} /></footer></button>;
}

export function RoomsPage({ data, onNavigate }: { data: OSBootstrap; onNavigate: (path: string) => void }) {
  const groups = ["NEEDS_INPUT", "ACTIVE", "WAITING_FOR_PEER", "COMPLETED", "CLOSED"];
  return <div className="standard-page"><PageHeading eyebrow="Task-scoped coordination" title="Coordination Rooms" copy="Inspect what agents discussed without mixing private instructions, agent negotiation, and shared human conversation." />{data.rooms.length ? groups.map((status) => {
    const rooms = data.rooms.filter((room) => room.status === status);
    if (!rooms.length) return null;
    return <section className="room-group" key={status}><h2>{status.replaceAll("_", " ")}</h2><div className="room-grid">{rooms.map((room) => <RoomCard key={room.room_id} room={room} taskTitle={data.tasks.find((task) => task.task_id === room.task_id)?.title || "Request"} onOpen={() => onNavigate(`/rooms/${room.room_id}`)} />)}</div></section>;
  }) : <EmptyState title="No rooms yet" body="Rooms appear when Qi contacts another Personal Agent for a published request." />}</div>;
}

export function CoordinationRoomPage({ data, room, busy, onNavigate, onMode, onSend }: { data: OSBootstrap; room: CoordinationRoom; busy: boolean; onNavigate: (path: string) => void; onMode: (mode: string) => void; onSend: (action: string, content: string) => void }) {
  const [channel, setChannel] = useState<"PRIVATE" | "AGENTS" | "SHARED">("AGENTS");
  const [content, setContent] = useState("");
  const messages = data.roomMessages.filter((item) => item.room_id === room.room_id && (channel === "AGENTS" ? item.visibility === "AGENTS_ONLY" : channel === "SHARED" ? item.visibility === "SHARED_ROOM" : item.visibility === "PRIVATE_USER_AGENT"));
  const peer = room.participant_agent_ids.find((id) => id !== "qi-agent") || "Peer Agent";
  const send = (action: string) => { if (content.trim()) { onSend(action, content.trim()); setContent(""); } };
  return <div className="room-page"><PageHeading eyebrow={room.room_type.replaceAll("_", " ")} title={`${formatAgent(peer)} · Coordination Room`} copy={data.tasks.find((task) => task.task_id === room.task_id)?.title} action={<StatusPill status={room.status} />} />
    <div className="room-toolbar"><button onClick={() => onNavigate(`/requests/${room.task_id}`)}>Back to request</button><label>Communication mode<select value={room.autonomy_mode} onChange={(event) => onMode(event.target.value)}><option value="AGENT">Agent mode</option><option value="COPILOT">Co-pilot mode</option><option value="HUMAN">Human mode</option></select></label></div>
    <nav className="channel-tabs"><button className={channel === "PRIVATE" ? "active" : ""} onClick={() => setChannel("PRIVATE")}><LockKeyhole size={15} /> Private with Qi</button><button className={channel === "AGENTS" ? "active" : ""} onClick={() => setChannel("AGENTS")}><Bot size={15} /> Agents-only transcript</button><button className={channel === "SHARED" ? "active" : ""} disabled={!room.human_participation_available} onClick={() => setChannel("SHARED")}><UsersRound size={15} /> Shared room</button></nav>
    <div className="room-transcript">{messages.length ? messages.map((message) => <article key={message.message_id}><span className="chat-avatar">{message.speaker_type === "HUMAN" ? <UserRound size={15} /> : <Bot size={15} />}</span><div><header><strong>{message.speaker_id === "qi-owner" ? "You" : formatAgent(message.speaker_id)}</strong><small>{message.authorship.replaceAll("_", " ")} · {message.visibility.replaceAll("_", " ")}</small></header><p>{message.content}</p><footer><Eye size={12} /> Provenance retained</footer></div></article>) : <EmptyState title={channel === "PRIVATE" ? "Private channel is clear" : channel === "SHARED" ? "Shared room is ready" : "No agent exchange yet"} body={channel === "PRIVATE" ? "Instructions here stay between you and Qi." : "Messages are always labeled by real authorship and visibility."} />}</div>
    <section className="room-composer"><textarea rows={3} value={content} onChange={(event) => setContent(event.target.value)} placeholder={channel === "PRIVATE" ? "Tell Qi privately…" : channel === "SHARED" ? "Write a message as yourself…" : "Ask Qi to draft or send within authority…"} /><div><span>{channel === "PRIVATE" ? <><LockKeyhole size={13} /> Never sent to the shared room</> : channel === "SHARED" ? <><UserRound size={13} /> Clearly labeled as you</> : <><ShieldCheck size={13} /> You cannot type directly into agents-only</>}</span>{channel === "PRIVATE" ? <button className="primary-action" disabled={busy} onClick={() => send("TELL_QI_PRIVATELY")}><MessageCircle size={14} /> Tell Qi privately</button> : channel === "SHARED" ? <button className="primary-action" disabled={busy || !room.human_participation_available} onClick={() => send("SEND_AS_MYSELF")}><Send size={14} /> Send as myself</button> : <><button className="quiet-button" disabled={busy} onClick={() => send("ASK_QI_TO_DRAFT")}>Ask Qi to draft</button><button className="primary-action" disabled={busy} onClick={() => send("ASK_QI_TO_SEND")}><Send size={14} /> Ask Qi to send</button></>}</div></section>
    {room.human_participation_available ? <div className="synthetic-warning"><UsersRound size={15} /><span><strong>Single-user demo boundary</strong> Any peer human is a clearly labeled synthetic demo participant. Generated text is never presented as a real human message.</span></div> : null}
  </div>;
}
