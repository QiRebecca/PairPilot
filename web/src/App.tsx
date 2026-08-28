import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import {
  Activity,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  CircleDot,
  Clock3,
  FileSearch,
  Fingerprint,
  GitBranch,
  LockKeyhole,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Dictionary = Record<string, unknown>;
type Tab = "overview" | "work" | "network" | "audit" | "memory";

interface IntentPost extends Dictionary {
  intent_id?: string;
  owner_agent_id?: string;
  public_title?: string;
  public_summary?: string;
  public_constraints?: {
    event?: string;
    location?: string;
    date_start?: string;
    date_end?: string;
    roommate_gender_preference?: string;
  };
  public_requirements?: string[];
  capacity_remaining?: number;
  status?: string;
  version?: number;
}

interface RunState extends Dictionary {
  runId?: string;
  status?: string;
}

interface Turn extends Dictionary {
  turnId?: string;
  selectedTool?: string;
  stateTransition?: string;
  latencyMs?: number;
  createdAt?: string;
}

interface Message extends Dictionary {
  messageId?: string;
  fromAgentId?: string;
  toAgentId?: string;
  fromIntentId?: string;
  toIntentId?: string;
  pairSessionId?: string;
  speechAct?: string;
  naturalLanguage?: string;
  route?: string;
}

interface ApprovalRequest extends Dictionary {
  runId?: string;
  proposalId?: string;
  proposalVersion?: number;
  status?: string;
  sourceIntentId?: string;
  targetIntentId?: string;
  candidateIdentitySummary?: string;
  sharedDates?: { start?: string; end?: string };
  soloDates?: string[];
  costDifferenceUsd?: number;
  delegatedMaximumUsd?: number;
  agreedTerms?: string[];
  remainingUncertainty?: string;
  recommendation?: string;
  informationDisclosed?: string[];
  informationRemainingPrivate?: string[];
  holdExpiresAt?: string;
}

interface Hold extends Dictionary {
  hold_id?: string;
  active?: boolean;
  expired?: boolean;
}

interface DemoState extends Dictionary {
  product: string;
  executionMode: string;
  exactModelId: string;
  activeIntent: IntentPost | null;
  intentRegistry: IntentPost[];
  peerIntents: IntentPost[];
  intentPairSessions: Dictionary[];
  run: RunState | null;
  turns: Turn[];
  messages: Message[];
  beliefs: Dictionary[];
  proposals: Dictionary[];
  holds: Hold[];
  approvalRequests: ApprovalRequest[];
  approvals: Dictionary[];
  matches: Dictionary[];
  relationships: Dictionary[];
  relationshipEvents: Dictionary[];
  memories: Dictionary[];
  protectedMemoryCount: number;
}

interface DraftReview {
  publicPost: IntentPost;
  agentOnly: {
    quiet_overnight_compatibility?: { importance?: string; source?: string };
    maximum_additional_cost_usd?: number;
    partial_date_overlap_allowed?: boolean;
  };
  protected: { count: number; summary: string; disclosure: string };
  fieldProvenance: Record<string, string>;
  uncertainties: string[];
}

interface ReviewForm {
  intentId: string;
  title: string;
  summary: string;
  event: string;
  location: string;
  dateStart: string;
  dateEnd: string;
  gender: string;
  publicRequirements: string;
  quietImportance: string;
  maximumCost: number;
  partialOverlap: boolean;
}

const sampleGoal = `Find me a female roommate for ICML in Seoul from July 6 to July 10.
A quiet overnight environment matters more than getting the lowest price.
I can accept partial date overlap if the additional cost stays below $70.`;

const emptyState: DemoState = {
  product: "PairPilot",
  executionMode: "LIVE GEMINI + GOOGLE ADK + A2A",
  exactModelId: "gemini-3.7-flash",
  activeIntent: null,
  intentRegistry: [],
  peerIntents: [],
  intentPairSessions: [],
  run: null,
  turns: [],
  messages: [],
  beliefs: [],
  proposals: [],
  holds: [],
  approvalRequests: [],
  approvals: [],
  matches: [],
  relationships: [],
  relationshipEvents: [],
  memories: [],
  protectedMemoryCount: 1,
};

const agentNames: Record<string, string> = {
  "qi-agent": "Qi Agent",
  "alice-agent": "Alice Agent",
  "maya-agent": "Maya Agent",
  "lena-agent": "Lena Agent",
};

const toolLabels: Record<string, string> = {
  inspect_relationship_network: "Inspected trusted relationships",
  search_open_intents: "Searched active intent posts",
  request_warm_introduction: "Asked Alice Agent for an introduction",
  contact_candidates: "Contacted owners of selected posts",
  record_candidate_disposition: "Recorded an evidence-based decision",
  calculate_candidate_plan_cost: "Calculated the partial-overlap cost",
  create_proposal: "Created a post-scoped proposal",
  accept_proposal: "Qi Agent accepted the current version",
  send_proposal: "Negotiated the proposal over A2A",
  place_soft_hold_and_request_user_approval: "Reserved post capacity and paused for you",
};

const tabs: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "work", label: "Agent Work" },
  { id: "network", label: "Network" },
  { id: "audit", label: "Audit" },
  { id: "memory", label: "Memory" },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

function agentLabel(value?: string) {
  return (value && agentNames[value]) || value || "Personal Agent";
}

function formatDate(value?: string, withTime = false) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(value));
}

function formFromReview(review: DraftReview): ReviewForm {
  const post = review.publicPost;
  const constraints = post.public_constraints || {};
  return {
    intentId: post.intent_id || "",
    title: post.public_title || "",
    summary: post.public_summary || "",
    event: constraints.event || "ICML",
    location: constraints.location || "Seoul",
    dateStart: constraints.date_start || "2026-07-06",
    dateEnd: constraints.date_end || "2026-07-10",
    gender: constraints.roommate_gender_preference || "female",
    publicRequirements: (post.public_requirements || []).join(", "),
    quietImportance:
      review.agentOnly.quiet_overnight_compatibility?.importance || "high",
    maximumCost: review.agentOnly.maximum_additional_cost_usd ?? 70,
    partialOverlap: review.agentOnly.partial_date_overlap_allowed ?? true,
  };
}

function StatusPill({ status }: { status?: string }) {
  return <span className={`status-pill status-${(status || "idle").toLowerCase()}`}>{status || "NOT PUBLISHED"}</span>;
}

function Metric({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function Composer({ busy, onDraft }: { busy: boolean; onDraft: (goal: string) => void }) {
  const [goal, setGoal] = useState("");
  return (
    <section className="composer-stage">
      <div className="eyebrow"><Sparkles size={14} /> Your personal agent is ready</div>
      <h1>What are you looking for?</h1>
      <p className="hero-copy">Tell your personal agent once. It will publish the request, coordinate with other agents, and bring you back only when a real decision is ready.</p>
      <label className="composer-box">
        <span>Describe the outcome and what matters most</span>
        <textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="I’m looking for…" rows={7} />
      </label>
      <div className="composer-actions">
        <button className="ghost-button" onClick={() => setGoal(sampleGoal)} disabled={busy}>Use example</button>
        <button className="primary-button" onClick={() => onDraft(goal)} disabled={busy || goal.trim().length < 20}>
          {busy ? <RefreshCw className="spin" size={16} /> : <Bot size={16} />}
          {busy ? "Qi Agent is drafting…" : "Draft with my agent"}
        </button>
      </div>
      <div className="promise-row">
        <span><ShieldCheck size={15} /> Privacy-aware by default</span>
        <span><Users size={15} /> Matches active needs, not profiles</span>
        <span><Fingerprint size={15} /> You approve the final effect</span>
      </div>
    </section>
  );
}

function DraftReviewView({ review, busy, onPublish }: { review: DraftReview; busy: boolean; onPublish: (form: ReviewForm) => void }) {
  const [form, setForm] = useState(() => formFromReview(review));
  const set = <K extends keyof ReviewForm>(key: K, value: ReviewForm[K]) => setForm((current) => ({ ...current, [key]: value }));
  return (
    <section className="review-stage">
      <div className="stage-heading">
        <div><div className="eyebrow"><FileSearch size={14} /> Draft · not yet published</div><h1>Review what your agent will publish</h1></div>
        <StatusPill status="DRAFT" />
      </div>
      <div className="review-grid">
        <article className="review-card public-card">
          <div className="section-label"><Send size={15} /> Public post</div>
          <label>Title<input value={form.title} onChange={(event) => set("title", event.target.value)} /></label>
          <label>Summary<textarea rows={4} value={form.summary} onChange={(event) => set("summary", event.target.value)} /></label>
          <div className="field-row"><label>Event<input value={form.event} onChange={(event) => set("event", event.target.value)} /></label><label>Location<input value={form.location} onChange={(event) => set("location", event.target.value)} /></label></div>
          <div className="field-row"><label>From<input type="date" value={form.dateStart} onChange={(event) => set("dateStart", event.target.value)} /></label><label>To<input type="date" value={form.dateEnd} onChange={(event) => set("dateEnd", event.target.value)} /></label></div>
          <label>Public requirements<input value={form.publicRequirements} onChange={(event) => set("publicRequirements", event.target.value)} /></label>
        </article>
        <div className="review-stack">
          <article className="review-card agent-card">
            <div className="section-label"><Bot size={15} /> Shared only with personal agents</div>
            <label>Quiet overnight compatibility<select value={form.quietImportance} onChange={(event) => set("quietImportance", event.target.value)}><option value="high">High priority</option><option value="medium">Medium priority</option><option value="low">Low priority</option></select></label>
            <div className="field-row"><label>Maximum additional cost<input type="number" value={form.maximumCost} onChange={(event) => set("maximumCost", Number(event.target.value))} /></label><label className="toggle-label"><input type="checkbox" checked={form.partialOverlap} onChange={(event) => set("partialOverlap", event.target.checked)} /> Allow partial date overlap</label></div>
          </article>
          <article className="review-card protected-card">
            <div className="section-label"><LockKeyhole size={15} /> Protected and never sent</div>
            <strong>{review.protected.count} protected sleep-related fact</strong>
            <p>{review.protected.disclosure}</p>
          </article>
          <article className="review-card authority-card">
            <div className="section-label"><Fingerprint size={15} /> Negotiation authority</div>
            <p>Your agent may negotiate partial overlap up to <strong>${form.maximumCost}</strong>. It cannot commit, book, pay, or reveal protected memory.</p>
          </article>
        </div>
      </div>
      {review.uncertainties.length > 0 && <div className="uncertainty"><CircleDot size={14} /> Agent inference to review: {review.uncertainties.join(" · ")}</div>}
      <div className="publish-row"><span>Publishing makes this request visible to eligible personal agents.</span><button className="primary-button" disabled={busy} onClick={() => onPublish(form)}>{busy ? <RefreshCw className="spin" size={16} /> : <Send size={16} />}{busy ? "Publishing…" : "Publish and let my agent handle it"}</button></div>
    </section>
  );
}

function CandidateCard({ intent, state }: { intent: IntentPost; state: DemoState }) {
  const agentId = intent.owner_agent_id || "";
  const messages = state.messages.filter((message) => message.fromAgentId === agentId || message.toAgentId === agentId);
  const disposition = state.beliefs.find((belief) => belief.subjectAgentId === agentId && belief.field === "qi_disposition");
  const matched = state.matches.some((match) => match.candidateAgentId === agentId);
  const targetApproval = state.approvalRequests.some((request) => request.targetIntentId === intent.intent_id);
  const label = matched ? "Matched" : disposition?.value === "WITHDRAW" ? "Conversation ended" : targetApproval ? "Proposal ready" : messages.length ? "Agent conversation active" : "Open request";
  return (
    <article className={`candidate-card ${matched ? "candidate-match" : ""}`}>
      <div className="candidate-top"><div><span>{agentLabel(agentId)}’s request</span><strong>{intent.public_title}</strong></div><StatusPill status={label.toUpperCase().replaceAll(" ", "_")} /></div>
      <p>{intent.public_summary}</p>
      <div className="candidate-meta"><span><Clock3 size={13} /> {formatDate(intent.public_constraints?.date_start)}–{formatDate(intent.public_constraints?.date_end)}</span><span><Activity size={13} /> {messages.length} A2A messages</span></div>
      {agentId === "maya-agent" && state.messages.some((message) => message.fromAgentId === "alice-agent") && <div className="route-note"><GitBranch size={14} /> Introduced through Alice Agent</div>}
      {disposition?.observableReason ? <div className="reason-note">Reason: {String(disposition.observableReason)}</div> : null}
    </article>
  );
}

function ApprovalCard({ state, busy, onApprove, onReject, onRevalidate }: { state: DemoState; busy: boolean; onApprove: () => void; onReject: () => void; onRevalidate: () => void }) {
  const request = state.approvalRequests.at(-1);
  const hold = state.holds.at(-1);
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  if (!request) return null;
  const expiresAt = request.holdExpiresAt ? new Date(request.holdExpiresAt).getTime() : 0;
  const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
  const expired = hold?.expired || remaining === 0;
  return (
    <section className="approval-panel">
      <div className="approval-heading"><div><div className="eyebrow"><Fingerprint size={14} /> Your decision · exact effect</div><h2>A three-night room share is ready</h2></div><div className={`countdown ${expired ? "expired" : ""}`}><Clock3 size={15} /> {expired ? "Hold expired" : `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`}</div></div>
      <div className="contract-grid">
        <div><span>Candidate</span><strong>{request.candidateIdentitySummary}</strong></div><div><span>Intent pair</span><strong>{request.sourceIntentId} ↔ {request.targetIntentId}</strong></div><div><span>Shared dates</span><strong>{formatDate(request.sharedDates?.start)}–{formatDate(request.sharedDates?.end)}</strong></div><div><span>Solo dates</span><strong>{(request.soloDates || []).map((item) => formatDate(item)).join(", ") || "None"}</strong></div><div><span>Additional cost</span><strong>${request.costDifferenceUsd} · within ${request.delegatedMaximumUsd}</strong></div><div><span>Proposal version</span><strong>Version {request.proposalVersion}</strong></div>
      </div>
      <div className="contract-detail"><div><span>Why your agent recommends this</span><p>{request.recommendation}</p></div><div><span>Remaining uncertainty</span><p>{request.remainingUncertainty}</p></div></div>
      <div className="disclosure-row"><div><ShieldCheck size={15} /><span><strong>Disclosed</strong>{(request.informationDisclosed || []).join(" · ")}</span></div><div><LockKeyhole size={15} /><span><strong>Still protected</strong>{(request.informationRemainingPrivate || []).join(" · ")}</span></div></div>
      <div className="approval-actions">{expired ? <button className="primary-button" disabled={busy} onClick={onRevalidate}><RefreshCw size={16} /> Revalidate offer</button> : <button className="primary-button approve-button" disabled={busy} onClick={onApprove}><Check size={16} /> Approve exact effect</button>}<button className="ghost-button" disabled={busy} onClick={onReject}><X size={16} /> Reject</button></div>
    </section>
  );
}

function MatchedResult({ state }: { state: DemoState }) {
  const match = state.matches.at(-1);
  if (!match) return null;
  return (
    <section className="matched-stage">
      <div className="match-mark"><CheckCircle2 size={30} /></div><div className="eyebrow">Match committed · refresh-safe</div><h1>You’re matched with Maya</h1><p>Both intent posts are closed to new contacts. The synthetic in-app introduction is now unlocked.</p>
      <div className="result-grid"><div><Check size={15} /><span>Your request</span><strong>MATCHED</strong></div><div><Check size={15} /><span>Maya’s request</span><strong>MATCHED</strong></div><div><Check size={15} /><span>Other negotiations</span><strong>RELEASED</strong></div><div><Check size={15} /><span>Introduction access</span><strong>UNLOCKED</strong></div></div>
      <div className="network-growth"><Network size={22} /><div><strong>Your agent’s network has grown.</strong><p>New Maya relationship · Alice introduction provenance · one editable hotel-sharing inference</p></div></div>
    </section>
  );
}

function ActiveOverview({ state, busy, onStart, onApprove, onReject, onRevalidate }: { state: DemoState; busy: boolean; onStart: () => void; onApprove: () => void; onReject: () => void; onRevalidate: () => void }) {
  const intent = state.activeIntent;
  if (!intent) return null;
  const contacted = new Set(state.messages.filter((message) => message.toAgentId && message.toAgentId !== "qi-agent").map((message) => message.toAgentId)).size;
  const warmIntroductions = state.turns.filter((turn) => turn.selectedTool === "request_warm_introduction").length;
  const activeSessions = state.intentPairSessions.filter((session) => ["ACTIVE", "PROPOSED", "HELD"].includes(String(session.status))).length;
  const matched = state.matches.length > 0;
  return (
    <div className="overview-stack">
      {matched && <MatchedResult state={state} />}
      {!matched && <>
        <section className="request-hero"><div><div className="eyebrow"><CircleDot size={14} /> My active request</div><h1>{intent.public_title}</h1><p>{intent.public_summary}</p><div className="request-meta"><StatusPill status={intent.status} /><span>{intent.public_constraints?.location}</span><span>{formatDate(intent.public_constraints?.date_start)}–{formatDate(intent.public_constraints?.date_end)}</span></div></div><div className="request-action">{intent.status === "OPEN" && !state.run ? <button className="primary-button" disabled={busy} onClick={onStart}><Play size={16} /> Start agent monitoring</button> : <div className="agent-working"><span className="pulse-dot" /><div><strong>{intent.status === "AWAITING_APPROVAL" ? "Your decision is ready" : "Qi Agent is handling it"}</strong><span>{state.run?.status || "Intent Registry monitoring"}</span></div></div>}</div></section>
        <section className="metrics-row"><Metric value={state.peerIntents.filter((item) => item.status === "OPEN").length} label="Relevant open posts" /><Metric value={contacted} label="Agents contacted" /><Metric value={warmIntroductions} label="Warm introductions" /><Metric value={activeSessions} label="Active negotiations" /><Metric value={state.proposals.length} label="Promising proposals" /></section>
        {state.approvalRequests.length > 0 && <ApprovalCard state={state} busy={busy} onApprove={onApprove} onReject={onReject} onRevalidate={onRevalidate} />}
        <section className="candidate-section"><div className="section-heading"><div><span>Live request landscape</span><h2>What your agent is working through</h2></div><small>Posts, not static profiles</small></div><div className="candidate-grid">{state.peerIntents.map((peer) => <CandidateCard key={peer.intent_id} intent={peer} state={state} />)}</div></section>
      </>}
    </div>
  );
}

function WorkView({ state }: { state: DemoState }) {
  return <section className="content-panel"><div className="section-heading"><div><span>Agent progress</span><h1>Work you can understand</h1></div><small>{state.turns.length} verified tool actions</small></div><div className="timeline">{state.turns.length === 0 ? <div className="empty-note">Publish and start monitoring to see Qi Agent’s live work.</div> : state.turns.map((turn, index) => <article key={turn.turnId || index}><div className="timeline-index">{index + 1}</div><div><strong>{toolLabels[turn.selectedTool || ""] || turn.selectedTool}</strong><p>{String(turn.stateTransition || "Completed")}</p></div><small>{turn.latencyMs || 0} ms</small></article>)}</div></section>;
}

function NetworkGraph({ state }: { state: DemoState }) {
  const active = new Set(state.messages.flatMap((message) => [message.fromAgentId, message.toAgentId]));
  const nodes: Node[] = [
    ["qi-agent", 310, 190, "Your request owner"], ["alice-agent", 30, 35, "Trusted introducer"], ["maya-agent", 610, 35, "Open intent owner"], ["lena-agent", 610, 340, "Open intent owner"],
  ].map(([id, x, y, subtitle]) => ({ id: String(id), position: { x: Number(x), y: Number(y) }, sourcePosition: Position.Right, targetPosition: Position.Left, className: "flow-agent", data: { label: <div className={`network-node ${active.has(String(id)) ? "active" : ""}`}><Bot size={17} /><div><strong>{agentLabel(String(id))}</strong><span>{String(subtitle)}</span></div><i /></div> } }));
  const edges: Edge[] = [
    { id: "qi-alice", source: "qi-agent", target: "alice-agent", label: "trusted relationship", animated: active.has("alice-agent") }, { id: "alice-maya", source: "alice-agent", target: "maya-agent", label: "introduction path", animated: active.has("maya-agent") }, { id: "qi-maya", source: "qi-agent", target: "maya-agent", label: "intent-scoped A2A", animated: active.has("maya-agent") }, { id: "qi-lena", source: "qi-agent", target: "lena-agent", label: "open-post discovery", animated: active.has("lena-agent") },
  ].map((edge) => ({ ...edge, type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: edge.animated ? "#caff6a" : "#4c554e" } }));
  return <section className="network-panel"><div className="section-heading"><div><span>Transparency view</span><h1>Relationship network + active intent paths</h1></div><small>Strategy is model-selected</small></div><div className="flow-wrap"><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.6} maxZoom={1.3} proOptions={{ hideAttribution: true }}><Background variant={BackgroundVariant.Dots} gap={24} size={1} /><Controls showInteractive={false} /></ReactFlow></div><div className="network-legend"><span><i className="legend-open" /> Open intent discovery</span><span><i className="legend-warm" /> Relationship introduction</span><span><i className="legend-a2a" /> Authenticated A2A</span></div></section>;
}

function AuditView({ state }: { state: DemoState }) {
  return <section className="content-panel"><div className="section-heading"><div><span>Technical evidence</span><h1>Intent-scoped A2A audit</h1></div><small>Peer claims remain non-authoritative</small></div><div className="audit-list">{state.messages.length === 0 ? <div className="empty-note">No agent messages yet.</div> : state.messages.map((message, index) => <article key={message.messageId || index}><div className="message-route"><strong>{agentLabel(message.fromAgentId)}</strong><ArrowRight size={14} /><strong>{agentLabel(message.toAgentId)}</strong><StatusPill status={message.speechAct} /></div><p>{message.naturalLanguage}</p><small>{message.fromIntentId} ↔ {message.toIntentId} · {message.pairSessionId}</small></article>)}</div></section>;
}

function MemoryView({ state }: { state: DemoState }) {
  const maya = state.relationships.find((item) => item.targetAgentId === "maya-agent");
  return <section className="content-panel"><div className="section-heading"><div><span>Committed-event learning</span><h1>Relationship memory</h1></div><small>Never written by peer text</small></div><div className="memory-grid"><article><Network size={19} /><span>Trusted foundation</span><strong>{state.relationships.length} provenance-backed relationships</strong><p>Alice remains the established coordination relationship.</p></article><article className={maya ? "memory-new" : ""}><Users size={19} /><span>Network growth</span><strong>{maya ? "Maya relationship added" : "No new relationship yet"}</strong><p>Created only after a human-approved committed match.</p></article><article><Sparkles size={19} /><span>Scoped inference</span><strong>{state.memories.length ? "Hotel-sharing preference learned" : "Waiting for a committed outcome"}</strong><p>Editable, scoped, and never promoted to hard authority.</p></article></div></section>;
}

export default function App() {
  const [state, setState] = useState<DemoState>(emptyState);
  const [review, setReview] = useState<DraftReview | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const next = await api<DemoState>("/api/demo/state");
    setState({ ...emptyState, ...next });
    return next;
  }, []);

  useEffect(() => { void refresh().catch((reason: Error) => setError(reason.message)); }, [refresh]);
  useEffect(() => {
    if (!review && state.activeIntent?.status === "DRAFT" && state.activeIntent.intent_id) {
      void api<DraftReview>(`/api/intents/${state.activeIntent.intent_id}/review`).then(setReview).catch((reason: Error) => setError(reason.message));
    }
  }, [review, state.activeIntent]);

  const act = async (work: () => Promise<void>) => { setBusy(true); setError(""); try { await work(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Something went wrong"); } finally { setBusy(false); } };
  const draft = (goal: string) => void act(async () => { const result = await api<DraftReview>("/api/intents/draft", { method: "POST", body: JSON.stringify({ raw_goal: goal }) }); setReview(result); await refresh(); });
  const publish = (form: ReviewForm) => void act(async () => { await api("/api/intents/publish", { method: "POST", body: JSON.stringify({ intent_id: form.intentId, public_title: form.title, public_summary: form.summary, event: form.event, location: form.location, date_start: form.dateStart, date_end: form.dateEnd, roommate_gender_preference: form.gender, public_requirements: form.publicRequirements.split(",").map((item) => item.trim()).filter(Boolean), quiet_overnight_compatibility_importance: form.quietImportance, maximum_additional_cost_usd: form.maximumCost, partial_date_overlap_allowed: form.partialOverlap }) }); setReview(null); await refresh(); });
  const reset = () => void act(async () => { await api("/api/demo/reset", { method: "POST", body: "{}" }); setReview(null); setTab("overview"); await refresh(); });
  const start = () => {
    const intentId = state.activeIntent?.intent_id;
    if (!intentId) return;
    setBusy(true); setError("");
    const stream = new EventSource(`/api/demo/run/stream?intent_id=${encodeURIComponent(intentId)}`);
    stream.addEventListener("snapshot", (event) => setState({ ...emptyState, ...(JSON.parse((event as MessageEvent).data) as DemoState) }));
    stream.addEventListener("complete", () => { stream.close(); setBusy(false); void refresh(); });
    stream.onerror = () => { stream.close(); setBusy(false); setError("The live agent stream ended unexpectedly. Current state is preserved."); void refresh(); };
  };
  const request = state.approvalRequests.at(-1);
  const approvalPayload = request && state.run ? { run_id: state.run.runId, proposal_id: request.proposalId, proposal_version: request.proposalVersion } : null;
  const approve = () => void act(async () => { if (!approvalPayload) return; await api("/api/demo/approve", { method: "POST", body: JSON.stringify({ ...approvalPayload, confirmation: `APPROVE VERSION ${approvalPayload.proposal_version}` }) }); await refresh(); });
  const reject = () => void act(async () => { if (!approvalPayload) return; await api("/api/demo/reject", { method: "POST", body: JSON.stringify(approvalPayload) }); await refresh(); });
  const revalidate = () => void act(async () => { if (!approvalPayload) return; await api("/api/demo/revalidate", { method: "POST", body: JSON.stringify(approvalPayload) }); await refresh(); });

  let view;
  if (tab === "work") view = <WorkView state={state} />;
  else if (tab === "network") view = <NetworkGraph state={state} />;
  else if (tab === "audit") view = <AuditView state={state} />;
  else if (tab === "memory") view = <MemoryView state={state} />;
  else if (review) view = <DraftReviewView review={review} busy={busy} onPublish={publish} />;
  else if (!state.activeIntent) view = <Composer busy={busy} onDraft={draft} />;
  else view = <ActiveOverview state={state} busy={busy} onStart={start} onApprove={approve} onReject={reject} onRevalidate={revalidate} />;

  return (
    <div className="app-shell">
      <header className="topbar"><button className="brand" onClick={() => setTab("overview")}><span className="brand-mark"><GitBranch size={18} /></span><span><strong>PairPilot</strong><small>Intent marketplace</small></span></button><nav>{tabs.map((item) => <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav><div className="top-actions"><div className="live-badge"><span /><div><strong>LIVE GEMINI + ADK + A2A</strong><small>{state.exactModelId}</small></div></div><button className="icon-button" title="Reset Demo" onClick={reset} disabled={busy}><RotateCcw size={16} /></button></div></header>
      {error && <div className="error-banner"><X size={15} /> {error}<button onClick={() => setError("")}>Dismiss</button></div>}
      <main>{view}</main>
      <footer><span>Agents choose strategy.</span><span>Infrastructure enforces truth, privacy, and authority.</span></footer>
    </div>
  );
}
