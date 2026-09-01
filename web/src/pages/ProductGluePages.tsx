import {
  Archive,
  Bell,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock3,
  LockKeyhole,
  Settings2,
  ShieldCheck,
  XCircle,
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

interface DecisionPayload {
  decisions: RecordValue[];
  open: RecordValue[];
  resolved: RecordValue[];
  open_count: number;
}
interface NotificationPayload {
  notifications: RecordValue[];
  categories: Record<string, RecordValue[]>;
  unread_count: number;
  settings: RecordValue;
}
interface AutonomyPayload {
  action_levels: Record<string, string>;
  locked_actions: string[];
  task_overrides: RecordValue[];
  activity: RecordValue[];
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const notificationCategories = [
  "ALL",
  "DECISION_REQUIRED",
  "CANDIDATE_CHANGE",
  "AGENT_MESSAGE",
  "PROPOSAL_UPDATE",
  "MATCH_UPDATE",
  "COMMUNITY_UPDATE",
  "SYSTEM",
];
const actionCopy: Record<string, string> = {
  DRAFT_POST: "Prepare a private Post draft.",
  PUBLISH_POST: "Publish an ordinary Post after requirements are complete.",
  SEARCH_POSTS: "Search active public Posts.",
  CONTACT_PERSONAL_AGENTS: "Start contact with another Personal Agent.",
  ASK_COMPATIBILITY_QUESTIONS: "Ask minimum-necessary compatibility questions.",
  NEGOTIATE_SOFT_PREFERENCES: "Negotiate preferences that do not commit you.",
  PLACE_TEMPORARY_HOLDS: "Reserve a short, reversible proposal hold.",
  OPEN_AGENT_ROOMS: "Open an Agents-only coordination Room.",
  DRAFT_SHARED_MESSAGES: "Draft a message for a shared Room.",
  SEND_SHARED_MESSAGES: "Send a shared message as your Agent.",
  SHARE_PROTECTED_INFORMATION:
    "Share protected identity or private information.",
  APPROVE_FINAL_COMMITMENT: "Approve a final plan and create a Match.",
};

export function DecisionInboxPage({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<DecisionPayload | null>(null);
  const [tab, setTab] = useState("OPEN");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    try {
      setPayload(await request<DecisionPayload>("/api/app/decisions"));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load decisions.",
      );
    }
  }, [request]);
  useEffect(() => {
    void load();
  }, [load]);
  async function resolve(decision: RecordValue, outcome: "APPROVE" | "REJECT") {
    const id = asString(decision.decision_id);
    setBusy(id);
    setError("");
    try {
      await request(`/api/app/decisions/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          outcome,
          confirmation:
            outcome === "APPROVE"
              ? asString(decision.required_confirmation) || null
              : null,
        }),
      });
      setNotice(
        outcome === "APPROVE"
          ? "Decision approved against the authoritative entity."
          : "Decision rejected.",
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Decision could not be resolved.",
      );
    } finally {
      setBusy("");
    }
  }
  const items = tab === "OPEN" ? payload?.open || [] : payload?.resolved || [];
  return (
    <div className="beta-page">
      <header className="page-title">
        <span className="eyebrow">ONE PLACE FOR HUMAN AUTHORITY</span>
        <h1>Decision Inbox</h1>
        <p>
          Review every action that requires you. Approvals always execute
          against current server state and exact proposal versions.
        </p>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      {!payload ? (
        <div className="community-loading">Loading Decision Inbox…</div>
      ) : (
        <>
          <nav className="decision-tabs">
            <button
              className={tab === "OPEN" ? "active" : ""}
              onClick={() => setTab("OPEN")}
            >
              Open <span>{payload.open_count}</span>
            </button>
            <button
              className={tab === "RESOLVED" ? "active" : ""}
              onClick={() => setTab("RESOLVED")}
            >
              Resolved <span>{payload.resolved.length}</span>
            </button>
          </nav>
          {items.length ? (
            <div className="decision-v2-list">
              {items.map((decision) => (
                <article key={asString(decision.decision_id)}>
                  <header>
                    <span className="status-pill">
                      {asString(decision.priority)} ·{" "}
                      {asString(decision.type).replaceAll("_", " ")}
                    </span>
                    <small>
                      <Clock3 size={12} />
                      {asString(decision.created_at)}
                    </small>
                  </header>
                  <h2>{asString(decision.title)}</h2>
                  <p>{asString(decision.summary)}</p>
                  <footer>
                    <button
                      className="secondary-button"
                      onClick={() => navigate(asString(decision.entity_route))}
                    >
                      Open source <ChevronRight size={14} />
                    </button>
                    {decision.status === "OPEN" &&
                    decision.can_resolve_inline ? (
                      <>
                        <button
                          className="primary-button"
                          disabled={busy === decision.decision_id}
                          onClick={() => void resolve(decision, "APPROVE")}
                        >
                          <CheckCircle2 size={14} />
                          Approve
                        </button>
                        <button
                          className="danger-button"
                          disabled={busy === decision.decision_id}
                          onClick={() => void resolve(decision, "REJECT")}
                        >
                          <XCircle size={14} />
                          Reject
                        </button>
                      </>
                    ) : decision.status === "OPEN" ? (
                      <span>Continue in the authoritative workflow</span>
                    ) : null}
                  </footer>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <CheckCircle2 />
              <h3>
                {tab === "OPEN"
                  ? "You’re all caught up"
                  : "No resolved decisions"}
              </h3>
              <p>
                Meaningful human-required actions appear here automatically.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function NotificationsPage({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<NotificationPayload | null>(null);
  const [category, setCategory] = useState("ALL");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [inApp, setInApp] = useState(true);
  const [push, setPush] = useState(false);
  const [meaningful, setMeaningful] = useState(true);
  const [quietStart, setQuietStart] = useState("");
  const [quietEnd, setQuietEnd] = useState("");
  const load = useCallback(async () => {
    try {
      const next = await request<NotificationPayload>("/api/app/notifications");
      setPayload(next);
      setInApp(next.settings.in_app_enabled !== false);
      setPush(Boolean(next.settings.browser_push_enabled));
      setMeaningful(next.settings.meaningful_events_only !== false);
      setQuietStart(asString(next.settings.quiet_hours_start));
      setQuietEnd(asString(next.settings.quiet_hours_end));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load notifications.",
      );
    }
  }, [request]);
  useEffect(() => {
    void load();
  }, [load]);
  const items = useMemo(
    () =>
      category === "ALL"
        ? payload?.notifications || []
        : payload?.categories[category] || [],
    [category, payload],
  );
  async function open(item: RecordValue) {
    const id = asString(item.notification_id);
    if (item.status === "UNREAD")
      await request(`/api/app/notifications/${id}/read`, { method: "PUT" });
    navigate(asString(item.entity_route));
  }
  async function archive(id: string) {
    await request(`/api/app/notifications/${id}/archived`, { method: "PUT" });
    await load();
  }
  async function readAll() {
    setBusy(true);
    try {
      await request("/api/app/notifications/read-all", { method: "PUT" });
      await load();
    } finally {
      setBusy(false);
    }
  }
  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await request("/api/app/notification-settings", {
        method: "PUT",
        body: JSON.stringify({
          in_app_enabled: inApp,
          browser_push_enabled: push,
          meaningful_events_only: meaningful,
          quiet_hours_start: quietStart || null,
          quiet_hours_end: quietEnd || null,
        }),
      });
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not save notification settings.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="beta-page">
      <header className="page-title notification-heading">
        <div>
          <span className="eyebrow">MEANINGFUL AGENT ACTIVITY</span>
          <h1>Notifications</h1>
          <p>
            Open the exact Request, Room, Match, Connection, Memory, or Decision
            that changed.
          </p>
        </div>
        <button
          className="secondary-button"
          disabled={busy || !payload?.unread_count}
          onClick={() => void readAll()}
        >
          Mark all read
        </button>
      </header>
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      {!payload ? (
        <div className="community-loading">Loading notifications…</div>
      ) : (
        <div className="notification-layout">
          <main>
            <nav className="notification-tabs">
              {notificationCategories.map((item) => (
                <button
                  key={item}
                  className={category === item ? "active" : ""}
                  onClick={() => setCategory(item)}
                >
                  {item.replaceAll("_", " ")}
                </button>
              ))}
            </nav>
            {items.length ? (
              <div className="notification-v2-list">
                {items
                  .filter((item) => item.status !== "ARCHIVED")
                  .map((item) => (
                    <article
                      className={item.status === "UNREAD" ? "unread" : ""}
                      key={asString(item.notification_id)}
                    >
                      <button onClick={() => void open(item)}>
                        <Bell size={17} />
                        <span>
                          <small>
                            {asString(item.category).replaceAll("_", " ")} ·{" "}
                            {asString(item.status)}
                          </small>
                          <strong>{asString(item.title)}</strong>
                          <p>{asString(item.body)}</p>
                        </span>
                        <ChevronRight size={15} />
                      </button>
                      <button
                        aria-label="Archive notification"
                        onClick={() =>
                          void archive(asString(item.notification_id))
                        }
                      >
                        <Archive size={13} />
                      </button>
                    </article>
                  ))}
              </div>
            ) : (
              <div className="empty-state compact">
                <Bell />
                <h3>No notifications here</h3>
                <p>Your Agent reports material changes, not every tool call.</p>
              </div>
            )}
          </main>
          <aside>
            <form className="notification-settings" onSubmit={saveSettings}>
              <Settings2 />
              <h2>Preferences</h2>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={inApp}
                  onChange={(event) => setInApp(event.target.checked)}
                />
                In-app notifications
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={meaningful}
                  onChange={(event) => setMeaningful(event.target.checked)}
                />
                Meaningful events only
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={push}
                  onChange={(event) => setPush(event.target.checked)}
                />
                Browser push
              </label>
              <p>
                Push remains off until this browser has an explicit registered
                consent token. No delivery is fabricated.
              </p>
              <label>
                Quiet hours start
                <input
                  type="time"
                  value={quietStart}
                  onChange={(event) => setQuietStart(event.target.value)}
                />
              </label>
              <label>
                Quiet hours end
                <input
                  type="time"
                  value={quietEnd}
                  onChange={(event) => setQuietEnd(event.target.value)}
                />
              </label>
              <button className="primary-button" disabled={busy}>
                Save preferences
              </button>
            </form>
          </aside>
        </div>
      )}
    </div>
  );
}

export function AutonomyCenterPage({ tasks }: { tasks: RecordValue[] }) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<AutonomyPayload | null>(null);
  const [levels, setLevels] = useState<Record<string, string>>({});
  const [taskId, setTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const next = await request<AutonomyPayload>("/api/app/autonomy");
      setPayload(next);
      setLevels(next.action_levels);
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load autonomy policies.",
      );
    }
  }, [request]);
  useEffect(() => {
    void load();
  }, [load]);
  async function save() {
    setBusy(true);
    setError("");
    try {
      await request("/api/app/autonomy", {
        method: "PUT",
        body: JSON.stringify({
          action_levels: levels,
          task_id: taskId || null,
        }),
      });
      setNotice(
        taskId ? "Task-specific policy saved." : "Global Agent policies saved.",
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not save autonomy policies.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="beta-page">
      <header className="page-title">
        <span className="eyebrow">ACTION-SPECIFIC AUTHORITY</span>
        <h1>Autonomy Center</h1>
        <p>
          Choose exactly what your Personal Agent may do automatically, must ask
          first, or must never do. Final commitment always asks.
        </p>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      {!payload ? (
        <div className="community-loading">Loading Agent authority…</div>
      ) : (
        <>
          <section className="autonomy-scope">
            <label>
              Editing policy for
              <select
                value={taskId}
                onChange={(event) => setTaskId(event.target.value)}
              >
                <option value="">Global defaults</option>
                {tasks.map((task) => (
                  <option
                    key={asString(task.task_id)}
                    value={asString(task.task_id)}
                  >
                    {asString(task.title)}
                  </option>
                ))}
              </select>
            </label>
            <span>
              <ShieldCheck size={14} />
              Task overrides do not rewrite global defaults.
            </span>
          </section>
          <div className="autonomy-action-list">
            {Object.entries(actionCopy).map(([action, description]) => {
              const locked = payload.locked_actions.includes(action);
              return (
                <article key={action}>
                  <div className="autonomy-icon">
                    {locked ? <LockKeyhole size={16} /> : <Bot size={16} />}
                  </div>
                  <div>
                    <h2>{action.replaceAll("_", " ")}</h2>
                    <p>{description}</p>
                    {locked ? (
                      <small>
                        Infrastructure-enforced: always asks the human.
                      </small>
                    ) : null}
                  </div>
                  <select
                    aria-label={`${action} policy`}
                    value={locked ? "ASK_FIRST" : levels[action] || "ASK_FIRST"}
                    disabled={locked || busy}
                    onChange={(event) =>
                      setLevels((current) => ({
                        ...current,
                        [action]: event.target.value,
                      }))
                    }
                  >
                    <option value="AUTOMATIC">Automatic</option>
                    <option value="ASK_FIRST">Ask first</option>
                    <option value="NEVER">Never</option>
                  </select>
                </article>
              );
            })}
          </div>
          <button
            className="primary-button autonomy-save"
            disabled={busy}
            onClick={() => void save()}
          >
            Save authority policies
          </button>
          <section className="autonomy-history">
            <h2>Authority activity</h2>
            {payload.activity.length ? (
              payload.activity.map((event) => (
                <article key={asString(event.activity_id)}>
                  <ShieldCheck size={14} />
                  <span>
                    <strong>
                      {asString(event.action).replaceAll("_", " ")} →{" "}
                      {asString(event.level).replaceAll("_", " ")}
                    </strong>
                    <small>
                      {asString(event.task_id) || "Global"} ·{" "}
                      {asString(event.created_at)}
                    </small>
                  </span>
                </article>
              ))
            ) : (
              <p>No policy changes recorded yet.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
