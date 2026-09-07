import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  FileText,
  History,
  LayoutDashboard,
  MessageCircle,
  MessagesSquare,
  Pause,
  Play,
  Search,
  ShieldCheck,
  StopCircle,
  UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { PersonalAgentChat } from "../components/PersonalAgentChat";

type RecordValue = Record<string, unknown>;
type WorkspaceTab =
  | "conversation"
  | "overview"
  | "post"
  | "candidates"
  | "rooms"
  | "activity"
  | "audit";

interface WorkspaceData {
  tasks: RecordValue[];
  conversations: RecordValue[];
  conversationMessages: RecordValue[];
  presentationDirectives: RecordValue[];
  decisions: RecordValue[];
  rooms: RecordValue[];
  matches: RecordValue[];
  myPosts: RecordValue[];
  relationships: RecordValue[];
  memories: RecordValue[];
  communities: RecordValue[];
  notifications: RecordValue[];
  candidateAssessments: RecordValue[];
  candidateRankEvents: RecordValue[];
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const asNumber = (value: unknown) => (typeof value === "number" ? value : 0);
const list = (value: unknown) => (Array.isArray(value) ? value : []);

const tabs: Array<[WorkspaceTab, string, typeof Bot]> = [
  ["conversation", "Conversation", MessageCircle],
  ["overview", "Overview", LayoutDashboard],
  ["post", "Post", FileText],
  ["candidates", "Candidates", UsersRound],
  ["rooms", "Agent Rooms", MessagesSquare],
  ["activity", "Activity", Activity],
  ["audit", "Audit", History],
];

export function RequestWorkspaceV2Page({
  taskId,
  data,
  refresh,
  navigate,
  initialTab = "conversation",
}: {
  taskId: string;
  data: WorkspaceData;
  refresh: () => Promise<void>;
  navigate: (path: string) => void;
  initialTab?: WorkspaceTab;
}) {
  const { request } = useAuth();
  const [tab, setTab] = useState<WorkspaceTab>(initialTab);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const task = data.tasks.find((item) => item.task_id === taskId);
  const post = data.myPosts.find((item) => item.task_id === taskId);
  const draft = (task?.agent_public_draft || {}) as RecordValue;
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [requirements, setRequirements] = useState("");
  const conversation = data.conversations.find(
    (item) => item.kind === "GLOBAL_PERSONAL_AGENT",
  );
  const messages = data.conversationMessages.filter(
    (item) => item.conversation_id === conversation?.conversation_id,
  );
  const candidates = useMemo(
    () =>
      data.candidateAssessments
        .filter((item) => item.task_id === taskId)
        .sort((a, b) => asNumber(a.current_rank) - asNumber(b.current_rank)),
    [data.candidateAssessments, taskId],
  );
  const rooms = data.rooms.filter(
    (item) =>
      item.task_id === taskId ||
      item.source_task_id === taskId ||
      item.target_task_id === taskId,
  );
  const decisions = data.decisions.filter(
    (item) => item.task_id === taskId && item.status === "OPEN",
  );
  const rankEvents = data.candidateRankEvents.filter(
    (item) => item.task_id === taskId,
  );

  useEffect(() => setTab(initialTab), [initialTab]);

  useEffect(() => {
    setTitle(asString(draft.public_title) || asString(task?.title));
    setSummary(asString(draft.public_summary) || asString(task?.goal));
    setRequirements(list(draft.public_requirements).map(String).join(", "));
  }, [draft.public_requirements, draft.public_summary, draft.public_title, task]);

  async function run(
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ): Promise<boolean> {
    setBusy(key);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      await refresh();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The action failed.");
      return false;
    } finally {
      setBusy("");
    }
  }

  async function closeRequest() {
    if (
      !window.confirm(
        "Close this Request? Its public Post will stop appearing, active candidate conversations will be withdrawn, and open decisions will be cancelled.",
      )
    )
      return;
    const closed = await run(
      "close-request",
      () =>
        request(`/api/app/tasks/${taskId}/close`, {
          method: "POST",
          body: "{}",
        }),
      "Request closed. It no longer counts toward your active Request limit.",
    );
    if (closed) navigate("/app/agent");
  }

  async function saveOrPublish(event: FormEvent, publish: boolean) {
    event.preventDefault();
    const body = JSON.stringify({
      public_title: title,
      public_summary: summary,
      public_requirements: requirements
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    await run(
      publish ? "publish" : "draft",
      () =>
        request(`/api/app/tasks/${taskId}/${publish ? "publish" : "draft"}`, {
          method: publish ? "POST" : "PUT",
          body,
        }),
      publish
        ? "Published. Your Agent is monitoring and evaluating compatible Posts."
        : "Draft saved. It will remain available when you return.",
    );
  }

  async function setPostStatus(status: "OPEN" | "PAUSED" | "CLOSED") {
    if (!post) return;
    await run(
      `post:${status}`,
      () =>
        request(`/api/app/posts/${asString(post.intent_id)}/status`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        }),
      `Post is now ${status.toLowerCase()}.`,
    );
  }

  async function candidateAction(
    candidate: RecordValue,
    action: "proposal" | "BACKUP" | "WITHDRAWN" | "NEEDS_INFORMATION",
  ) {
    const candidateId = asString(candidate.candidate_intent_id);
    await run(
      `candidate:${candidateId}:${action}`,
      () =>
        request(
          action === "proposal"
            ? `/api/app/tasks/${taskId}/candidates/${candidateId}/proposal`
            : `/api/app/tasks/${taskId}/candidates/${candidateId}/state`,
          {
            method: action === "proposal" ? "POST" : "PATCH",
            body: action === "proposal" ? "{}" : JSON.stringify({ state: action }),
          },
        ),
      action === "proposal"
        ? "A versioned proposal is ready for independent human review."
        : action === "WITHDRAWN"
          ? "Your Agent will stop contacting this candidate."
          : "Candidate state updated.",
    );
  }

  if (!task) {
    return (
      <div className="beta-page">
        <div className="empty-state">
          <CircleAlert />
          <h2>Request not found</h2>
          <p>This Request is not part of your authenticated account.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="beta-page request-workspace-v2">
      <header className="request-workspace-heading">
        <div>
          <span className="eyebrow">REQUEST WORKSPACE · PRIVATE CONTROL PLANE</span>
          <h1>{asString(task.title)}</h1>
          <p>
            Keep talking to the same Personal Agent. This workspace only changes
            the active task context; it never starts a disconnected assistant.
          </p>
        </div>
        <div className="request-workspace-heading-actions">
          <span className={`status-pill status-${asString(task.status).toLowerCase()}`}>
            {asString(task.status)}
          </span>
          {!["COMPLETED", "CANCELLED"].includes(asString(task.status)) ? (
            <button
              className="danger-button"
              disabled={Boolean(busy)}
              onClick={() => void closeRequest()}
            >
              <StopCircle size={14} />
              {busy === "close-request" ? "Closing…" : "Close Request"}
            </button>
          ) : null}
        </div>
      </header>
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="form-notice" role="status">
          {notice}
        </div>
      ) : null}
      <nav className="request-workspace-tabs" aria-label="Request workspace sections">
        {tabs.map(([id, name, Icon]) => (
          <button
            key={id}
            className={tab === id ? "active" : ""}
            aria-current={tab === id ? "page" : undefined}
            onClick={() => setTab(id)}
          >
            <Icon size={15} /> {name}
            {id === "overview" && decisions.length ? <b>{decisions.length}</b> : null}
            {id === "candidates" && candidates.length ? <b>{candidates.length}</b> : null}
          </button>
        ))}
      </nav>

      {tab === "conversation" ? (
        <PersonalAgentChat
          title="My Personal Agent"
          conversation={conversation}
          messages={messages}
          taskId={taskId}
          refresh={refresh}
          directives={data.presentationDirectives}
          tasks={data.tasks}
          posts={data.myPosts}
          decisions={data.decisions}
          rooms={data.rooms}
          matches={data.matches}
          connections={data.relationships}
          communities={data.communities}
          memories={data.memories}
          navigate={navigate}
        />
      ) : null}
      {tab === "overview" ? (
        <Overview
          task={task}
          post={post}
          candidates={candidates}
          rooms={rooms}
          decisions={decisions}
          navigate={navigate}
        />
      ) : null}
      {tab === "post" ? (
        <PostWorkspace
          post={post}
          title={title}
          summary={summary}
          requirements={requirements}
          busy={busy}
          setTitle={setTitle}
          setSummary={setSummary}
          setRequirements={setRequirements}
          onSave={(event) => void saveOrPublish(event, false)}
          onPublish={(event) => void saveOrPublish(event, true)}
          onStatus={(status) => void setPostStatus(status)}
          navigate={navigate}
        />
      ) : null}
      {tab === "candidates" ? (
        <Candidates
          candidates={candidates}
          busy={busy}
          navigate={navigate}
          onAction={(candidate, action) => void candidateAction(candidate, action)}
        />
      ) : null}
      {tab === "rooms" ? <AgentRooms rooms={rooms} navigate={navigate} /> : null}
      {tab === "activity" ? (
        <ActivityTimeline
          rankEvents={rankEvents}
          notifications={data.notifications.filter((item) => item.task_id === taskId)}
        />
      ) : null}
      {tab === "audit" ? (
        <RequestAudit
          task={task}
          post={post}
          candidates={candidates}
          decisions={decisions}
          rankEvents={rankEvents}
        />
      ) : null}
    </div>
  );
}

function Overview({
  task,
  post,
  candidates,
  rooms,
  decisions,
  navigate,
}: {
  task: RecordValue;
  post?: RecordValue;
  candidates: RecordValue[];
  rooms: RecordValue[];
  decisions: RecordValue[];
  navigate: (path: string) => void;
}) {
  const contacted = candidates.filter((item) => item.room_id || item.active_room_id);
  const primary = candidates.find((item) => asNumber(item.current_rank) === 1);
  const backups = candidates.filter((item) => item.state === "BACKUP");
  return (
    <div className="request-overview-v2">
      <section className="request-overview-summary">
        <div>
          <span>Current request</span>
          <h2>{asString(task.title)}</h2>
          <p>{asString(task.goal)}</p>
        </div>
        <span className="status-pill">{asString(task.status)}</span>
      </section>
      <div className="request-overview-grid">
        <Fact name="Community" value={asString(task.community_id) || "Not selected"} />
        <Fact name="Post status" value={asString(post?.status) || "DRAFT"} />
        <Fact name="Candidates discovered" value={String(candidates.length)} />
        <Fact name="Candidates contacted" value={String(contacted.length)} />
        <Fact name="Active negotiations" value={String(rooms.length)} />
        <Fact
          name="Primary candidate"
          value={asString(primary?.candidate_display_name) || "Not selected"}
        />
        <Fact name="Backup candidates" value={String(backups.length)} />
        <Fact name="Pending decisions" value={String(decisions.length)} />
        <Fact
          name="Latest material change"
          value={asString(task.last_material_change_at) || asString(task.updated_at) || "—"}
        />
        <Fact
          name="Background monitoring"
          value={post?.status === "OPEN" ? "ACTIVE" : "PAUSED"}
        />
      </div>
      {decisions.length ? (
        <section className="request-decision-list">
          <h2>Needs your input</h2>
          {decisions.map((decision) => (
            <button
              key={asString(decision.decision_id)}
              onClick={() => navigate("/app/decisions")}
            >
              <CheckCircle2 size={16} />
              <span>
                <strong>{asString(decision.title)}</strong>
                <small>{asString(decision.summary)}</small>
              </span>
            </button>
          ))}
        </section>
      ) : null}
    </div>
  );
}

function Fact({ name, value }: { name: string; value: string }) {
  return (
    <article>
      <small>{name}</small>
      <strong>{value}</strong>
    </article>
  );
}

function PostWorkspace({
  post,
  title,
  summary,
  requirements,
  busy,
  setTitle,
  setSummary,
  setRequirements,
  onSave,
  onPublish,
  onStatus,
  navigate,
}: {
  post?: RecordValue;
  title: string;
  summary: string;
  requirements: string;
  busy: string;
  setTitle: (value: string) => void;
  setSummary: (value: string) => void;
  setRequirements: (value: string) => void;
  onSave: (event: FormEvent) => void;
  onPublish: (event: FormEvent) => void;
  onStatus: (status: "OPEN" | "PAUSED" | "CLOSED") => void;
  navigate: (path: string) => void;
}) {
  if (post) {
    return (
      <section className="request-post-v2">
        <header>
          <div>
            <span className="eyebrow">AUTHORITATIVE PUBLIC PROJECTION</span>
            <h2>{asString(post.public_title)}</h2>
          </div>
          <span className="status-pill">{asString(post.status)}</span>
        </header>
        {post.public_summary ? <p>{asString(post.public_summary)}</p> : null}
        <div className="request-requirements">
          {list(post.public_requirements).map((item) => (
            <span key={String(item)}>{String(item)}</span>
          ))}
        </div>
        <p className="privacy-note">
          <ShieldCheck size={15} /> Only this public projection is discoverable.
          Private chat, constraints, and protected Memory remain private.
        </p>
        <div className="card-actions">
          <button
            className="primary-button"
            onClick={() => navigate(`/app/posts/${asString(post.intent_id)}`)}
          >
            Open Post Detail
          </button>
          <button
            disabled={Boolean(busy)}
            onClick={() => onStatus(post.status === "PAUSED" ? "OPEN" : "PAUSED")}
          >
            {post.status === "PAUSED" ? <Play size={14} /> : <Pause size={14} />}
            {post.status === "PAUSED" ? "Resume" : "Pause"}
          </button>
          <button
            className="danger-button"
            disabled={Boolean(busy) || post.status === "CLOSED"}
            onClick={() => onStatus("CLOSED")}
          >
            <StopCircle size={14} /> Close
          </button>
        </div>
      </section>
    );
  }
  return (
    <form className="request-post-form" onSubmit={onPublish}>
      <span className="eyebrow">PRIVATE DRAFT · REVIEW BEFORE PUBLICATION</span>
      <h2>Post drafted from your conversation</h2>
      <label>
        Public title
        <input value={title} onChange={(event) => setTitle(event.target.value)} required />
      </label>
      <label>
        Public description (optional)
        <textarea
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="No minimum length. Leave empty if the title is enough."
        />
      </label>
      <label>
        Public requirements and tags
        <input
          value={requirements}
          onChange={(event) => setRequirements(event.target.value)}
          placeholder="Separate with commas"
        />
      </label>
      <p className="privacy-note">
        <ShieldCheck size={15} /> Review the exact public projection. Agent-only
        constraints and protected Memory are excluded.
      </p>
      <div className="card-actions">
        <button
          type="button"
          disabled={Boolean(busy)}
          onClick={(event) => onSave(event)}
        >
          Save draft
        </button>
        <button className="primary-button" disabled={Boolean(busy)}>
          Approve & publish
        </button>
      </div>
    </form>
  );
}

function Candidates({
  candidates,
  busy,
  navigate,
  onAction,
}: {
  candidates: RecordValue[];
  busy: string;
  navigate: (path: string) => void;
  onAction: (
    candidate: RecordValue,
    action: "proposal" | "BACKUP" | "WITHDRAWN" | "NEEDS_INFORMATION",
  ) => void;
}) {
  if (!candidates.length) {
    return (
      <div className="empty-state">
        <Search />
        <h2>Your Agent is monitoring active Posts</h2>
        <p>
          Qualified candidates will appear here only after evidence-backed
          evaluation. No percentage score is fabricated.
        </p>
      </div>
    );
  }
  return (
    <div className="request-candidate-list">
      {candidates.map((candidate) => {
        const id = asString(candidate.candidate_intent_id);
        const roomId = asString(candidate.room_id || candidate.active_room_id);
        return (
          <article key={id}>
            <div className="request-candidate-rank">#{asNumber(candidate.current_rank)}</div>
            <div>
              <header>
                <div>
                  <span className="status-pill">{asString(candidate.state)}</span>
                  <h2>
                    {asString(candidate.candidate_display_name) || "Community member"}
                  </h2>
                </div>
                <strong>{asString(candidate.priority_band)}</strong>
              </header>
              <p>{asString(candidate.observable_explanation)}</p>
              <Evidence title="Verified" values={list(candidate.verified_support)} />
              <Evidence title="Peer-reported" values={list(candidate.peer_reported_support)} />
              <Evidence title="Conflicts" values={list(candidate.conflicts)} warning />
              <Evidence title="Uncertainties" values={list(candidate.uncertainties)} warning />
              <div className="card-actions">
                <button
                  className="primary-button"
                  disabled={Boolean(busy) || Boolean(candidate.proposal_id)}
                  onClick={() => onAction(candidate, "proposal")}
                >
                  {candidate.proposal_id ? "Proposal ready" : "Prepare proposal"}
                </button>
                {roomId ? (
                  <button onClick={() => navigate(`/app/rooms/${roomId}`)}>
                    Open Agent Room
                  </button>
                ) : null}
                <button
                  disabled={Boolean(busy)}
                  onClick={() => onAction(candidate, "BACKUP")}
                >
                  Keep as backup
                </button>
                <button
                  className="danger-button"
                  disabled={Boolean(busy)}
                  onClick={() => onAction(candidate, "WITHDRAWN")}
                >
                  Stop contacting
                </button>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function Evidence({
  title,
  values,
  warning = false,
}: {
  title: string;
  values: unknown[];
  warning?: boolean;
}) {
  if (!values.length) return null;
  return (
    <div className={warning ? "request-evidence warning" : "request-evidence"}>
      <strong>{title}</strong>
      <ul>
        {values.map((item, index) => (
          <li key={`${title}-${index}`}>
            {typeof item === "object" && item !== null
              ? asString((item as RecordValue).fact) || JSON.stringify(item)
              : String(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AgentRooms({
  rooms,
  navigate,
}: {
  rooms: RecordValue[];
  navigate: (path: string) => void;
}) {
  if (!rooms.length)
    return (
      <div className="empty-state">
        <MessagesSquare />
        <h2>No Agent Rooms yet</h2>
        <p>A task-scoped Room appears after your Agent contacts a candidate Agent.</p>
      </div>
    );
  return (
    <div className="request-room-list">
      {rooms.map((room) => (
        <button
          key={asString(room.room_id)}
          onClick={() => navigate(`/app/rooms/${asString(room.room_id)}`)}
        >
          <Bot size={18} />
          <span>
            <strong>{asString(room.title) || "Agent coordination Room"}</strong>
            <small>
              {asString(room.state || room.status)} · next {asString(room.next_expected_actor)}
            </small>
          </span>
        </button>
      ))}
    </div>
  );
}

function ActivityTimeline({
  rankEvents,
  notifications,
}: {
  rankEvents: RecordValue[];
  notifications: RecordValue[];
}) {
  const items: RecordValue[] = [
    ...rankEvents.map((item) => ({ ...item, kind: "RANKING_CHANGED" })),
    ...notifications.map((item) => ({ ...item, kind: asString(item.type) })),
  ];
  if (!items.length)
    return (
      <div className="empty-state">
        <Activity />
        <h2>No material activity yet</h2>
        <p>Routine tool calls are intentionally omitted. Material changes appear here.</p>
      </div>
    );
  return (
    <ol className="request-activity-list">
      {items.map((item, index) => (
        <li key={asString(item.event_id || item.notification_id) || String(index)}>
          <span />
          <div>
            <strong>{asString(item.title) || asString(item.kind).replaceAll("_", " ")}</strong>
            <p>{asString(item.body || item.summary || item.reason)}</p>
            <small>{asString(item.created_at || item.timestamp)}</small>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RequestAudit({
  task,
  post,
  candidates,
  decisions,
  rankEvents,
}: {
  task: RecordValue;
  post?: RecordValue;
  candidates: RecordValue[];
  decisions: RecordValue[];
  rankEvents: RecordValue[];
}) {
  const rows = [
    ["Task", asString(task.task_id), asString(task.status), asString(task.updated_at)],
    ...(post
      ? [["Post", asString(post.intent_id), asString(post.status), asString(post.updated_at)]]
      : []),
    ...candidates.map((item) => [
      "Candidate assessment",
      asString(item.assessment_id),
      asString(item.state),
      asString(item.last_material_change_at || item.updated_at),
    ]),
    ...decisions.map((item) => [
      "Decision",
      asString(item.decision_id),
      asString(item.status),
      asString(item.created_at),
    ]),
    ...rankEvents.map((item) => [
      "Ranking event",
      asString(item.rank_event_id || item.event_id),
      "IMMUTABLE",
      asString(item.created_at || item.timestamp),
    ]),
  ];
  return (
    <section className="request-audit-panel">
      <header>
        <History size={19} />
        <div>
          <h2>Authoritative object history</h2>
          <p>
            IDs, states, timestamps, and provenance only. Hidden reasoning is not
            presented as an audit record.
          </p>
        </div>
      </header>
      <div className="operations-table-wrap">
        <table className="operations-table">
          <thead>
            <tr>
              <th>Object</th>
              <th>ID</th>
              <th>State</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([kind, id, state, time]) => (
              <tr key={`${kind}:${id}`}>
                <td>{kind}</td>
                <td>{id}</td>
                <td>{state}</td>
                <td>{time || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
