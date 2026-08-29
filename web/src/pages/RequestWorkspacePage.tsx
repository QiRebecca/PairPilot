import { Activity, ArrowRight, Bot, Clock3, FileText, LayoutDashboard, MessageCircle, Scale, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import type { Assessment, DraftReview, OSBootstrap, PresentationDirective, TaskWorkspace } from "../types";
import { Conversation, DecisionCard, DraftReviewCard, EmptyState, PageHeading, StatusPill, TrustLegend, type ReviewForm } from "../components/ProductComponents";
import { formatAgent, formatDate } from "../utils";

type TaskTab = "conversation" | "overview" | "post" | "activity";

function CandidateAssessmentCard({ assessment, onRoom }: { assessment: Assessment; onRoom: () => void }) {
  return <article className={`assessment-card band-${assessment.priority_band.toLowerCase()}`}>
    <header><div><span>{formatAgent(assessment.candidate_agent_id)}</span><h3>{assessment.priority_band.replaceAll("_", " ")}</h3></div><StatusPill status={assessment.current_status} /></header>
    <p>{assessment.observable_explanation}</p>
    <div className="evidence-columns"><div><span><ShieldCheck size={13} /> Verified support</span>{assessment.verified_support.map((item) => <small key={item}>{item}</small>)}</div><div><span><Bot size={13} /> Peer-reported</span>{assessment.peer_reported_support.map((item) => <small key={item}>{item}</small>)}</div></div>
    {assessment.conflicts.length ? <div className="conflict-note">Conflict · {assessment.conflicts.join(" · ")}</div> : null}
    {assessment.uncertainties.length ? <div className="uncertainty-note">Uncertainty · {assessment.uncertainties.join(" · ")}</div> : null}
    <footer><span>{assessment.relationship_path.join(" → ")}</span>{assessment.active_room_id ? <button onClick={onRoom}>Open room <ArrowRight size={13} /></button> : null}</footer>
  </article>;
}

function TaskOverview({ data, task, onNavigate, busy, onApprove, onReject }: { data: OSBootstrap; task: TaskWorkspace; onNavigate: (path: string) => void; busy: boolean; onApprove: () => void; onReject: () => void }) {
  const assessments = data.candidateAssessments.filter((item) => item.task_id === task.task_id);
  const decisions = data.decisions.filter((item) => item.task_id === task.task_id && item.status === "OPEN");
  const rooms = data.rooms.filter((item) => item.task_id === task.task_id);
  const approval = data.demoState.approvalRequests.at(-1);
  return <div className="task-overview">
    <section className="task-summary-card"><div><span>Current goal</span><h2>{task.title}</h2><p>{task.goal}</p></div><StatusPill status={task.status} /></section>
    <section className="task-metrics"><div><strong>{data.explorePosts.filter((post) => post.status === "OPEN").length}</strong><span>relevant open posts</span></div><div><strong>{rooms.length}</strong><span>agent conversations</span></div><div><strong>{assessments.filter((item) => item.priority_band === "RECOMMENDED").length}</strong><span>recommended</span></div><div><strong>{decisions.length}</strong><span>needs your decision</span></div></section>
    {decisions.map((decision) => <DecisionCard key={decision.decision_id} decision={decision} approval={decision.type === "APPROVE_PROPOSAL" ? approval : undefined} busy={busy} onApprove={onApprove} onReject={onReject} onOpen={() => undefined} />)}
    <section><div className="section-title"><div><span>Candidate posts</span><h2>Qi’s current assessment</h2></div><TrustLegend /></div>{assessments.length ? <div className="assessment-grid">{assessments.map((assessment) => <CandidateAssessmentCard key={assessment.assessment_id} assessment={assessment} onRoom={() => onNavigate(`/rooms/${assessment.active_room_id}`)} />)}</div> : <EmptyState title="Qi is preparing the landscape" body="Publish the post to let Qi search active needs and communicate with multiple agents." />}</section>
  </div>;
}

function PostView({ data, task, review, busy, onPublish }: { data: OSBootstrap; task: TaskWorkspace; review: DraftReview | null; busy: boolean; onPublish: (form: ReviewForm) => void }) {
  const post = data.demoState.intentRegistry.find((item) => item.intent_id === task.intent_id) || data.demoState.activeIntent;
  if (review) return <DraftReviewCard review={review} busy={busy} onPublish={onPublish} />;
  if (!post) return <EmptyState title="Post unavailable" body="Qi has not created a post for this request yet." />;
  return <article className="published-post"><header><span><FileText size={14} /> Your intent post</span><StatusPill status={post.status} /></header><h2>{post.public_title}</h2><p>{post.public_summary}</p><div className="post-facts"><div><span>Event</span><strong>{post.public_constraints?.event}</strong></div><div><span>Location</span><strong>{post.public_constraints?.location}</strong></div><div><span>Dates</span><strong>{formatDate(post.public_constraints?.date_start)}–{formatDate(post.public_constraints?.date_end)}</strong></div><div><span>Capacity</span><strong>{post.capacity_remaining} remaining</strong></div></div><section><span>Public requirements</span><p>{post.public_requirements?.join(" · ")}</p></section><section className="authorship-block"><Bot size={17} /><div><strong>Drafted by Qi Agent</strong><small>{post.authorship?.approved_by_owner ? "Approved and published by you" : "Awaiting your approval"}</small></div></section></article>;
}

export function RequestWorkspacePage({ data, task, review, busy, onSend, onPublish, onNavigate, onDirective, onApprove, onReject }: {
  data: OSBootstrap; task: TaskWorkspace; review: DraftReview | null; busy: boolean;
  onSend: (content: string) => void; onPublish: (form: ReviewForm) => void;
  onNavigate: (path: string) => void; onDirective: (directive: PresentationDirective) => void;
  onApprove: () => void; onReject: () => void;
}) {
  const [tab, setTab] = useState<TaskTab>(task.status === "DRAFT" ? "post" : "conversation");
  useEffect(() => setTab(task.status === "DRAFT" ? "post" : "conversation"), [task.task_id, task.status]);
  const messages = data.conversationMessages.filter((item) => item.conversation_id === task.conversation_id);
  const taskTurns = data.demoState.turns;
  const tabs: { id: TaskTab; label: string; icon: typeof Bot }[] = [
    { id: "conversation", label: "Conversation", icon: MessageCircle },
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "post", label: "Post", icon: FileText },
    { id: "activity", label: "Activity", icon: Activity },
  ];
  return <div className="workspace-page">
    <PageHeading eyebrow="Request workspace" title={task.title} copy="This conversation and every agent room are isolated to this request." action={<StatusPill status={task.status} />} />
    <nav className="workspace-tabs">{tabs.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}><Icon size={15} /> {label}{id === "overview" && task.status === "NEEDS_DECISION" ? <b>1</b> : null}</button>)}</nav>
    {tab === "conversation" ? <Conversation title="Qi Agent · task conversation" subtitle={`Scoped to ${task.title}`} messages={messages} directives={data.presentationDirectives.filter((item) => item.task_id === task.task_id)} busy={busy} placeholder="Ask Qi about this request, compare candidates, or change the boundaries…" onSend={onSend} onDirective={onDirective} /> : null}
    {tab === "overview" ? <TaskOverview data={data} task={task} busy={busy} onNavigate={onNavigate} onApprove={onApprove} onReject={onReject} /> : null}
    {tab === "post" ? <PostView data={data} task={task} review={review} busy={busy} onPublish={onPublish} /> : null}
    {tab === "activity" ? <section className="activity-timeline">{taskTurns.length ? taskTurns.map((turn, index) => <article key={String(turn.turnId || index)}><span>{index + 1}</span><div><strong>{String(turn.selectedTool || "Agent action").replaceAll("_", " ")}</strong><p>{String(turn.stateTransition || "Completed")}</p></div><small><Clock3 size={12} /> {String(turn.latencyMs || 0)} ms</small></article>) : <EmptyState title="No agent actions yet" body="Actions will appear after the post is published." />}</section> : null}
    <div className="scope-proof"><Scale size={14} /> Task context: <code>{task.task_id}</code><span>•</span><UsersRound size={14} /> {data.rooms.filter((room) => room.task_id === task.task_id).length} isolated rooms</div>
  </div>;
}
