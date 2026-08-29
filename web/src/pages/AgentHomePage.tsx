import { Activity, ArrowRight, CheckCircle2, Clock3, MessageSquareMore, Sparkles } from "lucide-react";
import type { OSBootstrap, PresentationDirective } from "../types";
import { Conversation, DecisionCard, EmptyState } from "../components/ProductComponents";

export function AgentHomePage({ data, busy, onSend, onNavigate, onDirective, onApprove, onReject, onRevalidate }: {
  data: OSBootstrap;
  busy: boolean;
  onSend: (content: string) => void;
  onNavigate: (path: string) => void;
  onDirective: (directive: PresentationDirective) => void;
  onApprove: () => void;
  onReject: () => void;
  onRevalidate: () => void;
}) {
  const globalConversation = data.conversations.find((item) => item.kind === "GLOBAL_PERSONAL_AGENT");
  const messages = data.conversationMessages.filter((item) => item.conversation_id === globalConversation?.conversation_id);
  const openDecisions = data.decisions.filter((item) => item.status === "OPEN");
  const activeTasks = data.tasks.filter((item) => !["COMPLETED", "CANCELLED"].includes(item.status));
  const approval = data.demoState.approvalRequests.at(-1);
  const activeRooms = data.rooms.filter((room) => !["COMPLETED", "CLOSED"].includes(room.status));
  return <div className="agent-home-grid">
    <Conversation title="Qi Agent" subtitle="Your persistent Personal Agent" messages={messages} directives={data.presentationDirectives} busy={busy} placeholder="Tell Qi what you need, ask for an update, or change a preference…" onSend={onSend} onDirective={onDirective} />
    <aside className="context-rail">
      <section className="context-intro"><span><Sparkles size={14} /> Personal Agent OS</span><h2>Good to see you, Qi.</h2><p>Your agent carries bounded context across requests while keeping each task conversation isolated.</p></section>
      <section className="rail-section"><header><span>Needs your attention</span><b>{openDecisions.length}</b></header>{openDecisions.length ? openDecisions.slice(0, 2).map((decision) => <DecisionCard key={decision.decision_id} decision={decision} approval={decision.type === "APPROVE_PROPOSAL" ? approval : undefined} busy={busy} onApprove={onApprove} onReject={onReject} onRevalidate={onRevalidate} onOpen={() => decision.task_id && onNavigate(`/requests/${decision.task_id}`)} />) : <EmptyState title="You’re all caught up" body="Qi will surface only decisions that need your authority." />}</section>
      <section className="rail-section agent-stats"><header><span>Your agent is working on</span></header><div className="stat-row"><div><Activity size={16} /><strong>{activeTasks.length}</strong><span>active requests</span></div><div><MessageSquareMore size={16} /><strong>{activeRooms.length}</strong><span>agent conversations</span></div><div><Clock3 size={16} /><strong>{data.rooms.filter((room) => room.status === "WAITING_FOR_PEER").length}</strong><span>replies pending</span></div></div></section>
      <section className="rail-section result-list"><header><span>Recent results</span></header>{data.demoState.matches.length ? <button onClick={() => onNavigate("/matches")}><CheckCircle2 size={17} /><span><strong>Matched with Maya</strong><small>Both roommate posts closed</small></span><ArrowRight size={14} /></button> : <p className="rail-note">Committed outcomes will appear here.</p>}</section>
      <section className="rail-section"><header><span>What your agent learned</span></header>{data.demoState.memories.length ? <button className="memory-teaser" onClick={() => onNavigate("/memory")}><Sparkles size={16} /><span><strong>Partial dates can preserve quietness</strong><small>Review this scoped inference</small></span><ArrowRight size={14} /></button> : <p className="rail-note">Qi learns only from committed outcomes, never from untrusted peer text.</p>}</section>
    </aside>
  </div>;
}
