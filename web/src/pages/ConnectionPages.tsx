import {
  Bot,
  CircleAlert,
  GitBranch,
  MessageSquareMore,
  ShieldCheck,
  UserRoundX,
  UsersRound,
  Volume2,
  VolumeX,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import { useAuth } from "../auth";

type RecordValue = Record<string, unknown>;

interface ConnectionListPayload {
  connections: RecordValue[];
  views: Record<string, RecordValue[]>;
  count: number;
  graph: { nodes: RecordValue[]; edges: RecordValue[] };
}

interface ConnectionDetailPayload {
  connection: RecordValue;
  shared_communities: RecordValue[];
  plans: RecordValue[];
  active_rooms: RecordValue[];
  relationship_dimensions: RecordValue[];
  provenance_events: RecordValue[];
  usage_events: RecordValue[];
  shared_connections: RecordValue[];
  safety: RecordValue;
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const asNumber = (value: unknown) => (typeof value === "number" ? value : 0);
const tabs = [
  "ALL",
  "TRUSTED",
  "RECENT",
  "INTRODUCERS",
  "COMMUNITIES",
  "NEEDS_REVIEW",
  "BLOCKED",
  "GRAPH",
];

function person(connection: RecordValue): RecordValue {
  return (connection.person || {}) as RecordValue;
}
function agent(connection: RecordValue): RecordValue {
  return (connection.personal_agent || {}) as RecordValue;
}
function formatDate(value: unknown): string {
  const text = asString(value);
  if (!text) return "No interaction recorded";
  const date = new Date(text);
  return Number.isNaN(date.getTime())
    ? text
    : date.toLocaleDateString([], { dateStyle: "medium" });
}

export function ConnectionsPage({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<ConnectionListPayload | null>(null);
  const [tab, setTab] = useState("ALL");
  const [error, setError] = useState("");
  useEffect(() => {
    void request<ConnectionListPayload>("/api/app/connections")
      .then(setPayload)
      .catch((reason: Error) => setError(reason.message));
  }, [request]);
  const items = useMemo(() => payload?.views[tab] || [], [payload, tab]);
  return (
    <div className="beta-page">
      <header className="page-title">
        <span className="eyebrow">CONTEXTUAL RELATIONSHIPS</span>
        <h1>Connections</h1>
        <p>
          Use proven coordination history for future plans and warm
          introductions. PairPilot shows evidence by context instead of reducing
          a person to one score.
        </p>
      </header>
      {error ? <div className="form-error">{error}</div> : null}
      {!payload ? (
        <div className="community-loading">Loading Connections…</div>
      ) : payload.count === 0 ? (
        <div className="empty-state">
          <UsersRound />
          <h3>No Connection yet</h3>
          <p>
            A Connection begins from a mutually approved Match, then grows only
            through authoritative relationship events.
          </p>
        </div>
      ) : (
        <>
          <nav className="connection-tabs" aria-label="Connection views">
            {tabs.map((item) => (
              <button
                key={item}
                className={tab === item ? "active" : ""}
                onClick={() => setTab(item)}
              >
                {item.replaceAll("_", " ")}
                {item !== "GRAPH" ? (
                  <span>{(payload.views[item] || []).length}</span>
                ) : null}
              </button>
            ))}
          </nav>
          {tab === "GRAPH" ? (
            <ConnectionGraph graph={payload.graph} />
          ) : items.length ? (
            <div className="connection-list">
              {items.map((connection) => (
                <button
                  className="connection-card"
                  key={asString(connection.connection_id)}
                  onClick={() =>
                    navigate(
                      `/app/connections/${asString(connection.connection_id)}`,
                    )
                  }
                >
                  <div className="connection-avatar">
                    <UsersRound size={19} />
                  </div>
                  <div>
                    <header>
                      <span className="status-pill">
                        {asString(connection.state)}
                      </span>
                      <small>
                        {formatDate(connection.last_interaction_at)}
                      </small>
                    </header>
                    <h2>{asString(person(connection).display_name)}</h2>
                    <p>
                      <Bot size={13} />
                      {asString(agent(connection).display_name)}
                    </p>
                    <p>
                      {asString(connection.introduction_source).replaceAll(
                        "_",
                        " ",
                      )}{" "}
                      ·{" "}
                      {(Array.isArray(connection.task_contexts)
                        ? connection.task_contexts
                        : []
                      ).join(", ")}
                    </p>
                    <footer>
                      <span>
                        {asNumber(connection.completed_plans)} completed plans
                      </span>
                      <span>
                        {
                          (Array.isArray(connection.shared_community_ids)
                            ? connection.shared_community_ids
                            : []
                          ).length
                        }{" "}
                        shared communities
                      </span>
                    </footer>
                  </div>
                  <strong>Open →</strong>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <UsersRound />
              <h3>No Connections in this view</h3>
              <p>Try another relationship filter.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ConnectionGraph({ graph }: { graph: ConnectionListPayload["graph"] }) {
  return (
    <section
      className="connection-graph"
      aria-label="Secondary Connection graph"
    >
      <div className="graph-viewer">
        <UsersRound />
        <strong>You</strong>
      </div>
      <div className="graph-connections">
        {graph.nodes
          .filter((node) => node.kind === "CONNECTION")
          .map((node) => (
            <article key={asString(node.id)}>
              <Bot size={16} />
              <strong>{asString(node.label)}</strong>
              <small>{asString(node.state)}</small>
            </article>
          ))}
      </div>
      <p>
        <GitBranch size={14} />
        Edges represent your owner-scoped Connection records. No peer-private
        network is inferred.
      </p>
    </section>
  );
}

export function ConnectionDetailPage({
  connectionId,
  navigate,
}: {
  connectionId: string;
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<ConnectionDetailPayload | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);
  const load = useCallback(async () => {
    try {
      setPayload(
        await request<ConnectionDetailPayload>(
          `/api/app/connections/${connectionId}`,
        ),
      );
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load Connection.",
      );
    }
  }, [connectionId, request]);
  useEffect(() => {
    void load();
  }, [load]);
  async function act(
    name: string,
    action: () => Promise<unknown>,
    success: string,
  ) {
    setBusy(name);
    setNotice("");
    setError("");
    try {
      await action();
      setNotice(success);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The action failed.");
    } finally {
      setBusy("");
    }
  }
  function askAgent(message: string) {
    sessionStorage.setItem("pairpilot-agent-draft", message);
    navigate("/app/agent");
  }
  async function askIntroduction() {
    await act(
      "introduction",
      () =>
        request(`/api/app/connections/${connectionId}/usage`, {
          method: "POST",
          body: JSON.stringify({
            task_id: null,
            purpose: "REQUEST_WARM_INTRODUCTION",
          }),
        }),
      "Relationship context usage was recorded with provenance.",
    );
    askAgent(
      `Please inspect my Connection with ${asString(person(payload?.connection || {}).display_name)} and help me request an appropriate warm introduction. Ask me which active request this should apply to before contacting anyone.`,
    );
  }
  async function report(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await act(
      "report",
      () =>
        request("/api/app/reports", {
          method: "POST",
          body: JSON.stringify({
            target_type: "USER",
            target_id: asString(agent(payload?.connection || {}).agent_id),
            category: asString(form.get("category")),
            details: asString(form.get("details")),
          }),
        }),
      "Report submitted for authorized review.",
    );
    setReporting(false);
  }
  if (!payload)
    return (
      <div className="beta-page">
        {error ? (
          <div className="form-error">{error}</div>
        ) : (
          <div className="community-loading">Loading Connection Detail…</div>
        )}
      </div>
    );
  const connection = payload.connection;
  const peer = person(connection);
  const peerAgent = agent(connection);
  const muted = Boolean(connection.muted);
  const blocked = asString(connection.state) === "BLOCKED";
  return (
    <div className="beta-page connection-detail">
      <button
        className="text-button"
        onClick={() => navigate("/app/connections")}
      >
        ← All Connections
      </button>
      <header className="connection-detail-hero">
        <div className="connection-avatar large">
          <UsersRound size={25} />
        </div>
        <div>
          <span className="eyebrow">
            {asString(connection.state)} CONNECTION
          </span>
          <h1>{asString(peer.display_name)}</h1>
          <p>
            <Bot size={14} />
            {asString(peerAgent.display_name)} ·{" "}
            {asString(connection.introduction_source).replaceAll("_", " ")}
          </p>
        </div>
        <div className="connection-header-actions">
          <button
            className="primary-button"
            onClick={() =>
              askAgent(
                `Help me create another plan with ${asString(peer.display_name)}. Use only relationship evidence relevant to the new task, and ask me for the goal, community, date, and constraints.`,
              )
            }
          >
            Create another plan
          </button>
          <button
            className="secondary-button"
            disabled={!!busy || blocked}
            onClick={() => void askIntroduction()}
          >
            Ask for introduction
          </button>
          {payload.active_rooms[0] ? (
            <button
              className="secondary-button"
              onClick={() =>
                navigate(`/app/rooms/${asString(payload.active_rooms[0].room_id)}`)
              }
            >
              <MessageSquareMore size={14} /> Message in Room
            </button>
          ) : null}
        </div>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <div className="connection-detail-grid">
        <main>
          <section className="connection-panel">
            <h2>How you connected</h2>
            <dl>
              <div>
                <dt>Relationship</dt>
                <dd>
                  {asString(connection.how_connected).replaceAll("_", " ")}
                </dd>
              </div>
              <div>
                <dt>Introduction path</dt>
                <dd>
                  {asString(connection.introduction_source).replaceAll(
                    "_",
                    " ",
                  )}
                </dd>
              </div>
              <div>
                <dt>Relevant contexts</dt>
                <dd>
                  {(Array.isArray(connection.task_contexts)
                    ? connection.task_contexts
                    : []
                  ).join(", ") || "Not established"}
                </dd>
              </div>
              <div>
                <dt>Last interaction</dt>
                <dd>{formatDate(connection.last_interaction_at)}</dd>
              </div>
            </dl>
          </section>
          <section className="connection-panel">
            <h2>Relationship intelligence by dimension</h2>
            <p>
              No global score is calculated. Unknown evidence stays unknown.
            </p>
            <div className="connection-dimensions">
              {payload.relationship_dimensions.map((dimension) => (
                <article key={asString(dimension.dimension)}>
                  <strong>
                    {asString(dimension.dimension).replaceAll("_", " ")}
                  </strong>
                  <span>
                    {typeof dimension.value === "object"
                      ? Object.entries((dimension.value || {}) as RecordValue)
                          .map(
                            ([key, value]) =>
                              `${key.replaceAll("_", " ")}: ${String(value)}`,
                          )
                          .join(" · ")
                      : String(dimension.value ?? "Unknown")}
                  </span>
                  <small>{asString(dimension.evidence)}</small>
                </article>
              ))}
            </div>
          </section>
          <section className="connection-panel">
            <h2>Plans and active Rooms</h2>
            {payload.plans.length ? (
              <div className="connection-plan-list">
                {payload.plans.map((plan) => (
                  <button
                    key={asString(plan.match_id)}
                    onClick={() =>
                      navigate(`/app/matches/${asString(plan.match_id)}`)
                    }
                  >
                    <CheckPlan />
                    <span>
                      <strong>{asString(plan.title) || "Matched plan"}</strong>
                      <small>{asString(plan.state)}</small>
                    </span>
                    Open →
                  </button>
                ))}
              </div>
            ) : (
              <p className="subtle-copy">No shared plan is available.</p>
            )}
            {payload.active_rooms.map((room) => (
              <button
                className="connection-room-link"
                key={asString(room.room_id)}
                onClick={() => navigate(`/app/rooms/${asString(room.room_id)}`)}
              >
                <MessageSquareMore size={15} />
                Open active Room · {asString(room.state)}
              </button>
            ))}
          </section>
          <section className="connection-panel">
            <h2>Relationship-event provenance</h2>
            {payload.provenance_events.length ? (
              <div className="provenance-list">
                {payload.provenance_events.map((event) => (
                  <article key={asString(event.relationship_event_id)}>
                    <ShieldCheck size={15} />
                    <span>
                      <strong>
                        {asString(event.event_type).replaceAll("_", " ")}
                      </strong>
                      <small>
                        {asString(event.source).replaceAll("_", " ")} ·{" "}
                        {formatDate(event.created_at)}
                      </small>
                    </span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle-copy">No authoritative event is visible.</p>
            )}
          </section>
        </main>
        <aside>
          <section className="connection-panel">
            <h2>Shared Communities</h2>
            {payload.shared_communities.length ? (
              payload.shared_communities.map((community) => (
                <button
                  className="community-link-row"
                  key={asString(community.community_id)}
                  onClick={() =>
                    navigate(
                      `/app/communities/${asString(community.community_id)}`,
                    )
                  }
                >
                  {asString(community.name)} →
                </button>
              ))
            ) : (
              <p className="subtle-copy">No shared Community is recorded.</p>
            )}
          </section>
          <section className="connection-panel">
            <h2>Connection controls</h2>
            <button
              className="secondary-button full"
              disabled={!!busy || blocked}
              onClick={() =>
                void act(
                  "mute",
                  () =>
                    request(`/api/app/connections/${connectionId}/muted`, {
                      method: muted ? "DELETE" : "PUT",
                    }),
                  muted
                    ? "Connection notifications restored."
                    : "Connection muted.",
                )
              }
            >
              {muted ? <Volume2 size={14} /> : <VolumeX size={14} />}
              {muted ? "Unmute" : "Mute"}
            </button>
            <button
              className="secondary-button full"
              disabled={!!busy || blocked}
              onClick={() =>
                void act(
                  "remove",
                  () =>
                    request(
                      `/api/app/connections/${connectionId}/suggestions/removed`,
                      { method: "PUT" },
                    ),
                  "This Connection will not be suggested automatically.",
                )
              }
            >
              <UserRoundX size={14} />
              Remove from suggestions
            </button>
            <button
              className="danger-button full"
              disabled={!!busy || blocked}
              onClick={() =>
                void act(
                  "block",
                  () =>
                    request("/api/app/blocks", {
                      method: "POST",
                      body: JSON.stringify({
                        target_agent_id: asString(peerAgent.agent_id),
                        reason: "Blocked from Connection Detail",
                      }),
                    }),
                  "Blocked across future discovery and uncommitted coordination.",
                )
              }
            >
              <CircleAlert size={14} />
              {blocked ? "Blocked" : "Block"}
            </button>
            <button
              className="text-button full"
              disabled={!!busy}
              onClick={() => setReporting(!reporting)}
            >
              Report
            </button>
            {reporting ? (
              <form className="connection-report-form" onSubmit={report}>
                <select name="category" aria-label="Report category">
                  <option value="SAFETY">Safety</option>
                  <option value="HARASSMENT">Harassment</option>
                  <option value="MISREPRESENTATION">Misrepresentation</option>
                  <option value="OTHER">Other</option>
                </select>
                <textarea
                  name="details"
                  required
                  maxLength={1000}
                  placeholder="Describe what happened"
                />
                <button className="danger-button" disabled={!!busy}>
                  Submit report
                </button>
              </form>
            ) : null}
          </section>
          <section className="connection-panel relationship-usage">
            <h2>Relationship context usage</h2>
            {payload.usage_events.length ? (
              payload.usage_events.map((event) => (
                <article key={asString(event.usage_id)}>
                  <strong>
                    {asString(event.purpose).replaceAll("_", " ")}
                  </strong>
                  <small>
                    {event.context_applicable
                      ? "Applied in compatible context"
                      : "Not applied: context mismatch"}
                  </small>
                </article>
              ))
            ) : (
              <p className="subtle-copy">
                Your Agent has not used this Connection in a later task.
              </p>
            )}
            <p>
              <ShieldCheck size={12} />
              Every future use is scoped and recorded.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function CheckPlan() {
  return <ShieldCheck size={16} />;
}
