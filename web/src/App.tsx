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
  ChevronRight,
  CircleDot,
  Clock3,
  Database,
  Eye,
  Fingerprint,
  GitBranch,
  LockKeyhole,
  Network,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Dictionary = Record<string, unknown>;

interface RunState extends Dictionary {
  runId?: string;
  status?: string;
  exactModelId?: string;
}

interface Turn extends Dictionary {
  turnId?: string;
  selectedTool?: string;
  stateTransition?: string;
  latencyMs?: number;
  createdAt?: string;
  result?: Dictionary;
}

interface Message extends Dictionary {
  messageId?: string;
  fromAgentId?: string;
  toAgentId?: string;
  speechAct?: string;
  naturalLanguage?: string;
  route?: string;
}

interface ApprovalRequest extends Dictionary {
  proposalId?: string;
  proposalVersion?: number;
  status?: string;
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
  proposal_id?: string;
  active?: boolean;
  expired?: boolean;
}

interface DemoState extends Dictionary {
  product: string;
  executionMode: string;
  exactModelId: string;
  goal: string;
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

const emptyState: DemoState = {
  product: "PairPilot",
  executionMode: "LIVE GEMINI + GOOGLE ADK + A2A",
  exactModelId: "gemini-3.7-flash",
  goal:
    "Find me a female roommate for ICML in Seoul from July 6 to July 10. A quiet overnight environment matters more than getting the lowest price. I can accept partial date overlap if the additional cost stays below $70.",
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
  inspect_relationship_network: "Inspected the relationship network",
  search_open_agents: "Searched the open agent network",
  request_warm_introduction: "Asked Alice for a trusted introduction",
  contact_candidates: "Contacted selected personal agents in parallel",
  record_candidate_disposition: "Made an evidence-based candidate decision",
  calculate_candidate_plan_cost: "Calculated the partial-overlap cost",
  create_proposal: "Created a versioned proposal",
  accept_proposal: "Qi Agent accepted the proposal",
  send_proposal: "Negotiated the proposal over A2A",
  place_soft_hold_and_request_user_approval:
    "Placed a soft hold and paused for human approval",
};

function shortId(value?: string) {
  return value ? `${value.slice(0, 8)}…` : "Not started";
}

function agentLabel(id?: string) {
  return (id && agentNames[id]) || id || "Agent";
}

function formatDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

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

function AgentNode({ id, subtitle, tone }: { id: string; subtitle: string; tone: string }) {
  return (
    <div className={`agent-node ${tone}`}>
      <div className="agent-orbit" />
      <div className="agent-avatar">
        <Bot size={18} strokeWidth={1.8} />
      </div>
      <div>
        <strong>{agentLabel(id)}</strong>
        <span>{subtitle}</span>
      </div>
      <i aria-label="online" />
    </div>
  );
}

function NetworkGraph({ state }: { state: DemoState }) {
  const hasAliceMessage = state.messages.some(
    (message) => message.fromAgentId === "alice-agent",
  );
  const hasMayaMessage = state.messages.some(
    (message) => message.fromAgentId === "maya-agent",
  );
  const hasLenaMessage = state.messages.some(
    (message) => message.fromAgentId === "lena-agent",
  );
  const hasProposal = state.proposals.length > 0;
  const hasMatch = state.matches.length > 0;
  const lenaWithdrawn = state.beliefs.some(
    (belief) =>
      belief.subjectAgentId === "lena-agent" && belief.value === "WITHDRAW",
  );

  const nodes: Node[] = [
    {
      id: "qi-agent",
      position: { x: 308, y: 205 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: {
        label: <AgentNode id="qi-agent" subtitle="Your personal agent" tone="qi" />,
      },
      className: "flow-agent",
    },
    {
      id: "alice-agent",
      position: { x: 28, y: 32 },
      sourcePosition: Position.Right,
      targetPosition: Position.Bottom,
      data: {
        label: (
          <AgentNode
            id="alice-agent"
            subtitle={hasAliceMessage ? "Introduction offered" : "Trusted relationship"}
            tone="alice"
          />
        ),
      },
      className: "flow-agent",
    },
    {
      id: "maya-agent",
      position: { x: 600, y: 36 },
      sourcePosition: Position.Left,
      targetPosition: Position.Left,
      data: {
        label: (
          <AgentNode
            id="maya-agent"
            subtitle={
              hasMatch
                ? "New relationship"
                : hasProposal
                  ? "Proposal accepted"
                  : hasMayaMessage
                    ? "Active negotiation"
                    : "Open network"
            }
            tone="maya"
          />
        ),
      },
      className: "flow-agent",
    },
    {
      id: "lena-agent",
      position: { x: 610, y: 380 },
      sourcePosition: Position.Left,
      targetPosition: Position.Left,
      data: {
        label: (
          <AgentNode
            id="lena-agent"
            subtitle={
              lenaWithdrawn
                ? "Incompatible routine"
                : hasLenaMessage
                  ? "Evidence received"
                  : "Open network"
            }
            tone={lenaWithdrawn ? "muted" : "lena"}
          />
        ),
      },
      className: "flow-agent",
    },
  ];

  const edges: Edge[] = [
    {
      id: "qi-alice",
      source: "alice-agent",
      target: "qi-agent",
      label: "trusted prior coordination",
      animated: hasAliceMessage,
      className: "edge-trusted",
    },
    ...(hasAliceMessage
      ? [
          {
            id: "alice-maya",
            source: "alice-agent",
            target: "maya-agent",
            label: "warm introduction",
            animated: !hasProposal,
            className: "edge-intro",
            markerEnd: { type: MarkerType.ArrowClosed },
          } as Edge,
        ]
      : []),
    ...(hasMayaMessage
      ? [
          {
            id: "qi-maya",
            source: "qi-agent",
            target: "maya-agent",
            label: hasMatch ? "successful coordination" : hasProposal ? "proposal v1" : "A2A inquiry",
            animated: !hasMatch,
            className: hasMatch ? "edge-success" : "edge-active",
            markerEnd: { type: MarkerType.ArrowClosed },
          } as Edge,
        ]
      : []),
    ...(hasLenaMessage
      ? [
          {
            id: "qi-lena",
            source: "qi-agent",
            target: "lena-agent",
            label: lenaWithdrawn ? "withdrew — overnight conflict" : "A2A inquiry",
            animated: !lenaWithdrawn,
            className: lenaWithdrawn ? "edge-muted" : "edge-active",
            markerEnd: { type: MarkerType.ArrowClosed },
          } as Edge,
        ]
      : []),
  ];

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.12 }}
      minZoom={0.68}
      maxZoom={1.35}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#323733" />
      <Controls showInteractive={false} position="bottom-left" />
    </ReactFlow>
  );
}

function ApprovalCard({
  state,
  busy,
  onApprove,
  onReject,
}: {
  state: DemoState;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const request = state.approvalRequests.at(-1);
  const hold = state.holds.at(-1);
  if (!request) return null;
  const committed = state.matches.length > 0;
  const rejected = request.status === "REJECTED";
  const expired = hold?.expired === true || hold?.active === false;
  return (
    <section className={`approval-card ${committed ? "committed" : ""}`}>
      <div className="approval-kicker">
        {committed ? <Check size={14} /> : <Fingerprint size={14} />}
        {committed ? "Commit revalidated" : "Your authority boundary"}
      </div>
      <h3>
        {committed
          ? "Plan committed. The network learned."
          : rejected
            ? "Proposal rejected"
            : "One decision remains yours."}
      </h3>
      <p>{request.recommendation}</p>
      <div className="contract-grid">
        <div>
          <span>Shared dates</span>
          <strong>
            {request.sharedDates?.start?.slice(5)} → {request.sharedDates?.end?.slice(5)}
          </strong>
        </div>
        <div>
          <span>Solo coverage</span>
          <strong>{request.soloDates?.join(", ").slice(5)}</strong>
        </div>
        <div>
          <span>Cost difference</span>
          <strong>${request.costDifferenceUsd} / ${request.delegatedMaximumUsd}</strong>
        </div>
        <div>
          <span>Proposal</span>
          <strong>Version {request.proposalVersion}</strong>
        </div>
      </div>
      <div className="uncertainty">
        <Eye size={14} />
        <span>{request.remainingUncertainty}</span>
      </div>
      {!committed && !rejected && (
        <div className="approval-actions">
          <button className="button primary" onClick={onApprove} disabled={busy || expired}>
            <ShieldCheck size={16} />
            Approve exact effect
          </button>
          <button className="button ghost" onClick={onReject} disabled={busy || expired}>
            Reject
          </button>
        </div>
      )}
      {expired && !committed && !rejected && (
        <small className="expired-note">This hold expired safely. Reset and run again.</small>
      )}
      <div className="contract-foot">
        <LockKeyhole size={12} /> Raw private memory stays private
        <span>Hold until {formatDate(request.holdExpiresAt)}</span>
      </div>
    </section>
  );
}

function DetailDrawer({
  title,
  kind,
  state,
  onClose,
}: {
  title: string;
  kind: "audit" | "memory";
  state: DemoState;
  onClose: () => void;
}) {
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawer-head">
          <div>
            <span className="eyebrow">Observable, provenance-backed</span>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>
        {kind === "audit" ? (
          <div className="audit-list">
            {state.turns.map((turn, index) => (
              <article key={turn.turnId || index}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{toolLabels[turn.selectedTool || ""] || turn.selectedTool}</strong>
                  <p>{turn.stateTransition?.replaceAll("_", " ")}</p>
                </div>
                <small>{turn.latencyMs} ms</small>
              </article>
            ))}
            {state.turns.length === 0 && <div className="empty-copy">Start a run to see agent turns.</div>}
          </div>
        ) : (
          <div className="memory-list">
            {state.relationships.map((relationship, index) => (
              <article key={String(relationship._id || index)}>
                <GitBranch size={17} />
                <div>
                  <strong>
                    {agentLabel(String(relationship.sourceAgentId))} → {agentLabel(String(relationship.targetAgentId))}
                  </strong>
                  <p>{String(relationship.relationType).replaceAll("_", " ")}</p>
                  <small>Provenance: {String(relationship.provenanceEventIds)}</small>
                </div>
              </article>
            ))}
            {state.memories.map((memory, index) => (
              <article key={String(memory.memoryId || index)}>
                <Database size={17} />
                <div>
                  <strong>Scoped inferred memory</strong>
                  <p>{String(memory.summary || memory.content || "Provenance-backed coordination memory")}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState<DemoState>(emptyState);
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drawer, setDrawer] = useState<"audit" | "memory" | null>(null);
  const pausedRef = useRef(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const loadState = useCallback(async () => {
    try {
      setState(await api<DemoState>("/api/demo/state"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load demo state.");
    }
  }, []);

  useEffect(() => {
    void loadState();
    return () => eventSourceRef.current?.close();
  }, [loadState]);

  const startRun = () => {
    if (running) return;
    setError("");
    setRunning(true);
    setPaused(false);
    pausedRef.current = false;
    const source = new EventSource("/api/demo/run/stream");
    eventSourceRef.current = source;
    source.addEventListener("snapshot", (event) => {
      if (!pausedRef.current) setState(JSON.parse((event as MessageEvent).data) as DemoState);
    });
    source.addEventListener("complete", () => {
      source.close();
      eventSourceRef.current = null;
      setRunning(false);
      void loadState();
    });
    source.onerror = () => {
      source.close();
      eventSourceRef.current = null;
      setRunning(false);
      setError("The live stream closed. Reloading durable state from Firestore.");
      void loadState();
    };
  };

  const togglePause = () => {
    const next = !paused;
    setPaused(next);
    pausedRef.current = next;
    if (!next) void loadState();
  };

  const reset = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/api/demo/reset", { method: "POST" });
      setState(await api<DemoState>("/api/demo/state"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  };

  const approval = state.approvalRequests.at(-1);
  const approve = async () => {
    if (!state.run?.runId || !approval?.proposalId || !approval.proposalVersion) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/demo/approve", {
        method: "POST",
        body: JSON.stringify({
          run_id: state.run.runId,
          proposal_id: approval.proposalId,
          proposal_version: approval.proposalVersion,
          confirmation: `APPROVE VERSION ${approval.proposalVersion}`,
        }),
      });
      await loadState();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Approval failed safely.");
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!state.run?.runId || !approval?.proposalId || !approval.proposalVersion) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/demo/reject", {
        method: "POST",
        body: JSON.stringify({
          run_id: state.run.runId,
          proposal_id: approval.proposalId,
          proposal_version: approval.proposalVersion,
        }),
      });
      await loadState();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Rejection failed.");
    } finally {
      setBusy(false);
    }
  };

  const latestTurns = useMemo(() => state.turns.slice(-6).reverse(), [state.turns]);
  const runStatus = running ? (paused ? "FEED PAUSED" : "COORDINATING") : state.run?.status || "READY";

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="PairPilot home">
          <span className="brand-mark"><Network size={20} /></span>
          <span>PairPilot</span>
        </a>
        <div className="live-proof">
          <span className={`live-dot ${running ? "pulsing" : ""}`} />
          <strong>LIVE GEMINI + ADK + A2A</strong>
          <span>{state.exactModelId}</span>
        </div>
        <div className="run-meta">
          <span>Run {shortId(state.run?.runId)}</span>
          <span className={`status-pill status-${runStatus.toLowerCase().replaceAll("_", "-").replaceAll(" ", "-")}`}>
            {runStatus}
          </span>
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <CircleDot size={15} /> {error}
          <button onClick={() => setError("")} aria-label="Dismiss"><X size={15} /></button>
        </div>
      )}

      <section className="workspace" id="top">
        <aside className="panel context-panel">
          <div className="panel-heading">
            <span className="eyebrow">Personal agent</span>
            <h1>One intent.<br />A network at work.</h1>
            <p>Qi sets the outcome. PairPilot handles the social coordination.</p>
          </div>

          <div className="goal-card">
            <div className="card-label"><Sparkles size={14} /> Current goal</div>
            <p>{state.goal}</p>
          </div>

          <div className="priority-stack">
            <div>
              <span className="priority-rank">01</span>
              <div><strong>Quiet overnight fit</strong><small>Dominant preference</small></div>
            </div>
            <div>
              <span className="priority-rank">02</span>
              <div><strong>July 6–10 coverage</strong><small>Partial overlap allowed</small></div>
            </div>
            <div>
              <span className="priority-rank">03</span>
              <div><strong>≤ $70 extra</strong><small>Delegated cost boundary</small></div>
            </div>
          </div>

          <div className="boundary-card">
            <div><LockKeyhole size={15} /><span>Commitment boundary</span></div>
            <strong>Human approval required</strong>
            <p>Your agent can search, contact, negotiate, and hold—but cannot commit.</p>
          </div>

          <div className="privacy-row">
            <ShieldCheck size={16} />
            <div><strong>{state.protectedMemoryCount} protected fact</strong><span>Never sent to peer agents</span></div>
            <ChevronRight size={15} />
          </div>
        </aside>

        <section className="panel network-panel">
          <div className="network-head">
            <div>
              <span className="eyebrow">Live agent network</span>
              <h2>Relationships are infrastructure.</h2>
            </div>
            <div className="network-legend">
              <span><i className="legend-trusted" /> trusted</span>
              <span><i className="legend-live" /> live A2A</span>
              <span><i className="legend-new" /> learned</span>
            </div>
          </div>
          <div className="graph-wrap">
            <NetworkGraph state={state} />
            {!state.run && (
              <div className="graph-empty">
                <Network size={24} />
                <strong>The network is ready.</strong>
                <span>Start a live run to watch relationships activate.</span>
              </div>
            )}
          </div>
          <div className="message-strip">
            <div className="message-strip-label"><Activity size={14} /> A2A channel</div>
            {state.messages.at(-1) ? (
              <div className="latest-message">
                <span>{agentLabel(state.messages.at(-1)?.fromAgentId)}</span>
                <p>“{state.messages.at(-1)?.naturalLanguage}”</p>
                <small>{state.messages.at(-1)?.speechAct?.replaceAll("_", " ")}</small>
              </div>
            ) : (
              <div className="latest-message empty">No messages yet. The UI never replays a canned sequence.</div>
            )}
          </div>
        </section>

        <aside className="panel decisions-panel">
          <div className="decision-head">
            <div><span className="eyebrow">Observable decisions</span><h2>Why, without hidden reasoning.</h2></div>
            <button className="icon-button" onClick={() => setDrawer("audit")} aria-label="Inspect audit log"><Activity size={17} /></button>
          </div>

          <div className="timeline">
            {latestTurns.map((turn, index) => (
              <article key={turn.turnId || index} className={index === 0 ? "current" : ""}>
                <span className="timeline-dot">{index === 0 && running ? <RefreshCw size={11} /> : <Check size={11} />}</span>
                <div>
                  <small>{turn.selectedTool?.replaceAll("_", " ")}</small>
                  <strong>{toolLabels[turn.selectedTool || ""] || turn.selectedTool}</strong>
                  <p>{turn.stateTransition?.replaceAll("_", " ")}</p>
                </div>
                <time>{turn.latencyMs} ms</time>
              </article>
            ))}
            {latestTurns.length === 0 && (
              <div className="decision-empty">
                <GitBranch size={20} />
                <strong>No scripted path.</strong>
                <p>Live Gemini chooses tools after the run starts.</p>
              </div>
            )}
          </div>

          <ApprovalCard state={state} busy={busy} onApprove={() => void approve()} onReject={() => void reject()} />
        </aside>
      </section>

      <footer className="control-dock">
        <div className="dock-proof">
          <span><Database size={14} /> Firestore truth</span>
          <span><GitBranch size={14} /> Pub/Sub events</span>
          <span><ShieldCheck size={14} /> Authority enforced</span>
        </div>
        <div className="dock-actions">
          <button className="button ghost" onClick={() => void reset()} disabled={busy || running}>
            <RotateCcw size={16} /> Reset demo
          </button>
          <button className="button ghost" onClick={togglePause} disabled={!running}>
            {paused ? <Play size={16} /> : <Pause size={16} />} {paused ? "Resume feed" : "Pause feed"}
          </button>
          <button className="button ghost" onClick={() => setDrawer("audit")}>
            <Fingerprint size={16} /> Audit log
          </button>
          <button className="button ghost" onClick={() => setDrawer("memory")}>
            <Network size={16} /> Relationship memory
          </button>
          <button className="button primary start" onClick={startRun} disabled={running || busy}>
            {running ? <RefreshCw className="spin" size={17} /> : <Play size={17} />}
            {running ? "Agents coordinating" : "Start live run"}
            {!running && <ArrowRight size={16} />}
          </button>
        </div>
        <div className="dock-clock"><Clock3 size={14} /> 90-second hard bound</div>
      </footer>

      {drawer && (
        <DetailDrawer
          title={drawer === "audit" ? "Agent audit log" : "Relationship memory"}
          kind={drawer}
          state={state}
          onClose={() => setDrawer(null)}
        />
      )}
    </main>
  );
}
