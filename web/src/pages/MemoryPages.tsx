import {
  Archive,
  CheckCircle2,
  CircleAlert,
  Eye,
  EyeOff,
  History,
  MemoryStick,
  Pencil,
  ShieldCheck,
  Trash2,
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

interface MemoryWorkspacePayload {
  memories: RecordValue[];
  groups: Record<string, RecordValue[]>;
  count: number;
}

interface MemoryDetailPayload {
  memory: RecordValue;
  usage_events: RecordValue[];
  why_this_was_used: RecordValue[];
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const asNumber = (value: unknown) => (typeof value === "number" ? value : 0);
const groups = [
  "ABOUT_ME",
  "PREFERENCES",
  "BOUNDARIES",
  "ROUTINES",
  "COMMUNICATION",
  "TASK_SPECIFIC",
  "RELATIONSHIPS",
  "WAITING_FOR_CONFIRMATION",
  "RECENTLY_USED",
  "ARCHIVED",
];

export function MemoryPage({ navigate }: { navigate: (path: string) => void }) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<MemoryWorkspacePayload | null>(null);
  const [group, setGroup] = useState("WAITING_FOR_CONFIRMATION");
  const [error, setError] = useState("");
  useEffect(() => {
    void request<MemoryWorkspacePayload>("/api/app/memories")
      .then((next) => {
        setPayload(next);
        if (!(next.groups.WAITING_FOR_CONFIRMATION || []).length)
          setGroup("PREFERENCES");
      })
      .catch((reason: Error) => setError(reason.message));
  }, [request]);
  const items = useMemo(() => payload?.groups[group] || [], [group, payload]);
  return (
    <div className="beta-page">
      <header className="page-title">
        <span className="eyebrow">USER-CONTROLLED AGENT MODEL</span>
        <h1>Memory</h1>
        <p>
          Review exactly what your Personal Agent may use, where it applies, and
          why it influenced later work. Proposed Memory remains inert until you
          confirm it.
        </p>
      </header>
      {error ? <div className="form-error">{error}</div> : null}
      {!payload ? (
        <div className="community-loading">Loading Memory…</div>
      ) : payload.count === 0 ? (
        <div className="empty-state actionable-empty">
          <MemoryStick />
          <h3>No retained Memory</h3>
          <p>
            Keep talking to your Personal Agent and complete real plans. It can
            propose useful preferences with a source and scope; nothing becomes
            reusable until you confirm it.
          </p>
          <button className="primary-button" onClick={() => navigate("/app/agent")}>
            Talk to my Agent
          </button>
        </div>
      ) : (
        <>
          <section className="memory-overview-strip" aria-label="Memory summary">
            <article><strong>{payload.count}</strong><span>Total retained</span></article>
            <article><strong>{(payload.groups.WAITING_FOR_CONFIRMATION || []).length}</strong><span>Waiting for you</span></article>
            <article><strong>{(payload.groups.RECENTLY_USED || []).length}</strong><span>Recently used</span></article>
            <article><strong>{(payload.groups.ARCHIVED || []).length}</strong><span>Archived</span></article>
          </section>
          <nav className="memory-tabs" aria-label="Memory categories">
            {groups.map((item) => (
              <button
                key={item}
                className={group === item ? "active" : ""}
                onClick={() => setGroup(item)}
              >
                {item.replaceAll("_", " ")}
                <span>{(payload.groups[item] || []).length}</span>
              </button>
            ))}
          </nav>
          {items.length ? (
            <div className="memory-v2-grid">
              {items.map((memory) => (
                <button
                  className="memory-v2-card"
                  key={asString(memory.memory_id)}
                  onClick={() =>
                    navigate(`/app/memory/${asString(memory.memory_id)}`)
                  }
                >
                  <header>
                    <MemoryStick size={17} />
                    <span className="status-pill">
                      {asString(memory.status)}
                    </span>
                  </header>
                  <h2>{asString(memory.content) || "Deleted Memory"}</h2>
                  <dl>
                    <div>
                      <dt>Type</dt>
                      <dd>
                        {asString(memory.memory_type).replaceAll("_", " ")}
                      </dd>
                    </div>
                    <div>
                      <dt>Scope</dt>
                      <dd>{asString(memory.scope)}</dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>{asString(memory.source).replaceAll("_", " ")}</dd>
                    </div>
                    <div>
                      <dt>Usage</dt>
                      <dd>{asNumber(memory.usage_count)} recorded</dd>
                    </div>
                  </dl>
                  <footer>
                    <span>
                      {memory.disabled ? (
                        <>
                          <EyeOff size={12} />
                          Disabled
                        </>
                      ) : memory.usage_count ? (
                        <>
                          <History size={12} />
                          Recently used
                        </>
                      ) : (
                        <>
                          <ShieldCheck size={12} />
                          Not recently used
                        </>
                      )}
                    </span>
                    <strong>Review →</strong>
                  </footer>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <MemoryStick />
              <h3>No Memory in this category</h3>
              <p>Select another category to review your Agent model.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function MemoryDetailPage({
  memoryId,
  navigate,
}: {
  memoryId: string;
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<MemoryDetailPayload | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState("");
  const [scope, setScope] = useState("");
  const [deletePhrase, setDeletePhrase] = useState("");
  const load = useCallback(async () => {
    try {
      const next = await request<MemoryDetailPayload>(
        `/api/app/memories/${memoryId}`,
      );
      setPayload(next);
      setContent(asString(next.memory.content));
      setScope(asString(next.memory.scope));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load Memory.",
      );
    }
  }, [memoryId, request]);
  useEffect(() => {
    void load();
  }, [load]);
  async function act(action: string, body: RecordValue = {}) {
    setBusy(action);
    setNotice("");
    setError("");
    try {
      await request(`/api/app/memories/${memoryId}/actions`, {
        method: "POST",
        body: JSON.stringify({ action, content: null, scope: null, ...body }),
      });
      setNotice(
        action === "CONFIRM" || action === "EDIT_AND_CONFIRM"
          ? "Memory confirmed. It may now be used only within its recorded scope."
          : "Memory control updated.",
      );
      setEditing(false);
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not update Memory.",
      );
    } finally {
      setBusy("");
    }
  }
  async function editAndConfirm(event: FormEvent) {
    event.preventDefault();
    await act("EDIT_AND_CONFIRM", { content, scope });
  }
  if (!payload)
    return (
      <div className="beta-page">
        {error ? (
          <div className="form-error">{error}</div>
        ) : (
          <div className="community-loading">Loading Memory Detail…</div>
        )}
      </div>
    );
  const memory = payload.memory;
  const status = asString(memory.status);
  const confirmed = status === "CONFIRMED";
  const disabled = Boolean(memory.disabled);
  return (
    <div className="beta-page memory-detail">
      <button className="text-button" onClick={() => navigate("/app/memory")}>
        ← All Memory
      </button>
      <header className="memory-detail-hero">
        <MemoryStick size={28} />
        <div>
          <span className="eyebrow">
            {asString(memory.memory_type).replaceAll("_", " ")}
          </span>
          <h1>{asString(memory.content) || "Deleted Memory"}</h1>
          <p>
            <span className="status-pill">{status}</span> Scope:{" "}
            {asString(memory.scope)}
          </p>
        </div>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      <div className="memory-detail-grid">
        <main>
          <section className="memory-panel">
            <h2>Authority and provenance</h2>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{status}</dd>
              </div>
              <div>
                <dt>Confirmation</dt>
                <dd>
                  {asString(memory.confirmation_status) || "Not confirmed"}
                </dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{asString(memory.memory_type).replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>Scope</dt>
                <dd>{asString(memory.scope)}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{asString(memory.source).replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{asString(memory.confidence).replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>Sensitivity</dt>
                <dd>{asString(memory.sensitivity)}</dd>
              </div>
              <div>
                <dt>Usage count</dt>
                <dd>{asNumber(memory.usage_count)}</dd>
              </div>
            </dl>
            {Array.isArray(memory.provenance_event_ids) &&
            memory.provenance_event_ids.length ? (
              <p>Provenance events: {memory.provenance_event_ids.join(", ")}</p>
            ) : (
              <p>No external provenance event is attached.</p>
            )}
          </section>
          <section className="memory-panel">
            <h2>Why this was used</h2>
            {payload.usage_events.length ? (
              <div className="memory-usage-list">
                {payload.usage_events.map((event, index) => (
                  <article key={asString(event.usage_id)}>
                    <History size={16} />
                    <div>
                      <strong>
                        {asString(event.purpose).replaceAll("_", " ")}
                      </strong>
                      <p>
                        {asString(
                          payload.why_this_was_used[index]?.explanation,
                        )}
                      </p>
                      <small>
                        {asString(event.task_type) || "Global context"} ·{" "}
                        {asString(event.created_at)}
                      </small>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state compact">
                <History />
                <h3>Never used</h3>
                <p>
                  This Memory has not influenced an Agent context or
                  recommendation.
                </p>
              </div>
            )}
          </section>
          {editing ? (
            <section className="memory-panel">
              <h2>Edit and confirm</h2>
              <form className="memory-edit-form" onSubmit={editAndConfirm}>
                <label>
                  Memory content
                  <textarea
                    required
                    maxLength={2000}
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                  />
                </label>
                <label>
                  Scope
                  <input
                    required
                    maxLength={120}
                    value={scope}
                    onChange={(event) => setScope(event.target.value)}
                  />
                </label>
                <p>
                  Use GLOBAL only for a long-term preference. Use TASK:task_id,
                  TASK_TYPE:type, or RELATIONSHIP:id for narrower context.
                </p>
                <button className="primary-button" disabled={!!busy}>
                  <Pencil size={14} />
                  Save and confirm
                </button>
              </form>
            </section>
          ) : null}
        </main>
        <aside>
          <section className="memory-panel">
            <h2>Memory controls</h2>
            {!confirmed && status !== "ARCHIVED" && status !== "REJECTED" ? (
              <>
                <button
                  className="primary-button full"
                  disabled={!!busy}
                  onClick={() => void act("CONFIRM")}
                >
                  <CheckCircle2 size={14} />
                  Confirm as written
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() => setEditing(!editing)}
                >
                  <Pencil size={14} />
                  Edit and confirm
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() => void act("REJECT")}
                >
                  <XCircle size={14} />
                  Reject
                </button>
              </>
            ) : null}
            {confirmed ? (
              <>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() => setEditing(!editing)}
                >
                  <Pencil size={14} />
                  Edit and reconfirm
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() =>
                    void act(disabled ? "ENABLE" : "TEMPORARILY_DISABLE")
                  }
                >
                  {disabled ? <Eye size={14} /> : <EyeOff size={14} />}
                  {disabled ? "Enable" : "Temporarily disable"}
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() =>
                    void act("RESTRICT_SCOPE", {
                      scope: scope || "PRIVATE_ONLY",
                    })
                  }
                >
                  <ShieldCheck size={14} />
                  Restrict to current scope
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() => void act("STOP_USING")}
                >
                  <CircleAlert size={14} />
                  Stop using for matching
                </button>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() => void act("ARCHIVE")}
                >
                  <Archive size={14} />
                  Archive
                </button>
              </>
            ) : null}
          </section>
          <section className="memory-panel memory-delete">
            <h2>Delete Memory</h2>
            <p>
              Deletion blanks the retained content while preserving the minimum
              audit record.
            </p>
            <input
              aria-label="Memory deletion confirmation"
              value={deletePhrase}
              onChange={(event) => setDeletePhrase(event.target.value)}
              placeholder="DELETE MEMORY"
            />
            <button
              className="danger-button full"
              disabled={!!busy || deletePhrase !== "DELETE MEMORY"}
              onClick={() => void act("DELETE")}
            >
              <Trash2 size={14} />
              Delete permanently
            </button>
          </section>
        </aside>
      </div>
    </div>
  );
}
