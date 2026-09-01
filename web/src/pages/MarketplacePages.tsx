import {
  ArrowLeft,
  Bot,
  Bookmark,
  BookmarkCheck,
  CalendarDays,
  BellRing,
  Flag,
  MapPin,
  Search,
  ShieldAlert,
  Tags,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth";

type RecordValue = Record<string, unknown>;

const asString = (value: unknown) => (typeof value === "string" ? value : "");

interface PostDetailResponse {
  post: RecordValue;
  saved: boolean;
}

interface SearchResponse {
  items: RecordValue[];
  count: number;
  view: string;
  retrieval: {
    structured_filters: boolean;
    semantic_vector: boolean;
    text_relevance: boolean;
    note: string;
  };
}

const MARKETPLACE_VIEWS = [
  ["FOR_YOUR_REQUESTS", "For your Requests"],
  ["FROM_COMMUNITIES", "Communities"],
  ["FROM_CONNECTIONS", "Connections"],
  ["LATEST", "Latest"],
  ["SAVED", "Saved"],
  ["MY_POSTS", "My Posts"],
] as const;
const SUPPORTED_INTENT_TYPES = new Set([
  "ROOM_SHARE",
  "MEAL_COMPANION",
  "COFFEE_CHAT",
  "EVENT_BUDDY",
  "HACKATHON_TEAMMATE",
]);

export function MarketplaceExplorePage({
  tasks,
  myPosts,
  communities,
  navigate,
}: {
  tasks: RecordValue[];
  myPosts: RecordValue[];
  communities: RecordValue[];
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [view, setView] = useState("FOR_YOUR_REQUESTS");
  const [query, setQuery] = useState("");
  const [taskId, setTaskId] = useState("");
  const [communityId, setCommunityId] = useState("");
  const [intentType, setIntentType] = useState("");
  const [location, setLocation] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const activeTasks = useMemo(
    () =>
      tasks.filter(
        (task) =>
          !["COMPLETED", "CANCELLED"].includes(asString(task.status)) &&
          SUPPORTED_INTENT_TYPES.has(asString(task.task_type).toUpperCase()) &&
          myPosts.some(
            (post) => post.task_id === task.task_id && post.status === "OPEN",
          ),
      ),
    [myPosts, tasks],
  );

  useEffect(() => {
    if (!taskId && activeTasks.length) setTaskId(asString(activeTasks[0].task_id));
  }, [activeTasks, taskId]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setError("");
      void request<SearchResponse>("/api/app/explore/search", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          query,
          view,
          task_id: view === "FOR_YOUR_REQUESTS" && taskId ? taskId : null,
          community_id: communityId || null,
          intent_type: intentType || null,
          location: location || null,
          minimum_capacity: view === "MY_POSTS" ? 0 : 1,
          limit: 30,
        }),
      })
        .then(setResult)
        .catch((reason: Error) => {
          if (!controller.signal.aborted) setError(reason.message);
        });
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [communityId, intentType, location, query, request, taskId, view]);

  async function saveAndMonitor() {
    setSaving(true);
    setError("");
    try {
      await request("/api/app/saved-searches", {
        method: "POST",
        body: JSON.stringify({
          name: query.trim() || MARKETPLACE_VIEWS.find(([id]) => id === view)?.[1],
          monitor_enabled: true,
          notification_sensitivity: "MEANINGFUL",
          search: {
            query,
            view,
            task_id: view === "FOR_YOUR_REQUESTS" && taskId ? taskId : null,
            community_id: communityId || null,
            intent_type: intentType || null,
            location: location || null,
            minimum_capacity: view === "MY_POSTS" ? 0 : 1,
            limit: 30,
          },
        }),
      });
      setNotice("Saved. Your Agent will monitor this search for meaningful new Posts.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this search.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="beta-page marketplace-page">
      <header className="page-title">
        <span className="eyebrow">ACTIVE INTENT MARKETPLACE</span>
        <h1>Explore Posts, not profiles.</h1>
        <p>Search current needs inside trusted Communities. Your Personal Agent evaluates evidence and contacts the other Agent before people exchange details.</p>
      </header>
      <nav className="marketplace-tabs" aria-label="Marketplace views">
        {MARKETPLACE_VIEWS.map(([id, label]) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}>{label}</button>)}
      </nav>
      <section className="marketplace-search-panel">
        <label className="explore-search"><Search size={17} /><input aria-label="Natural-language Post search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try: dinner after the AI keynote with someone interested in agents" /></label>
        <div className="marketplace-filters">
          {view === "FOR_YOUR_REQUESTS" ? <label>Request<select value={taskId} onChange={(event) => setTaskId(event.target.value)}><option value="">All active Requests</option>{activeTasks.map((task) => <option key={asString(task.task_id)} value={asString(task.task_id)}>{asString(task.title)}</option>)}</select></label> : null}
          <label>Community<select value={communityId} onChange={(event) => setCommunityId(event.target.value)}><option value="">All joined</option>{communities.map((community) => <option key={asString(community.community_id)} value={asString(community.community_id)}>{asString(community.name)}</option>)}</select></label>
          <label>Type<select value={intentType} onChange={(event) => setIntentType(event.target.value)}><option value="">All types</option><option value="ROOM_SHARE">Room share</option><option value="MEAL_COMPANION">Meal companion</option><option value="COFFEE_CHAT">Coffee chat</option><option value="EVENT_BUDDY">Event buddy</option><option value="HACKATHON_TEAMMATE">Hackathon teammate</option></select></label>
          <label>Location<input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="City or venue" /></label>
          <button className="secondary-button monitor-search" disabled={saving} onClick={() => void saveAndMonitor()}><BellRing size={15} />{saving ? "Saving…" : "Save & monitor"}</button>
        </div>
      </section>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <div className="marketplace-result-heading"><strong>{result ? `${result.count} Posts` : "Searching…"}</strong><small>{result?.retrieval.semantic_vector ? "Structured + semantic retrieval" : "Structured + text relevance; vector index pending candidate backfill"}</small></div>
      {result?.items.length ? <div className="explore-grid">{result.items.map((post) => { const requirements = Array.isArray(post.public_requirements) ? post.public_requirements.map(String) : []; const reasons = Array.isArray(post.surfaced_reasons) ? post.surfaced_reasons.map(String) : []; return <button className="explore-card explore-card-button" key={asString(post.intent_id)} onClick={() => navigate(`/app/posts/${asString(post.intent_id)}`)}><span className={`status-pill status-${asString(post.status).toLowerCase()}`}>{post.saved ? "SAVED" : asString(post.status)}</span><h2>{asString(post.public_title)}</h2><p>{asString(post.public_summary)}</p>{requirements.length ? <div className="tag-row">{requirements.slice(0, 4).map((item) => <span key={item}><Tags size={11} />{item}</span>)}</div> : null}<div className="surfaced-reason"><Search size={14} /><small>{reasons.join(" · ")}</small></div><footer><span>Open direct Post Detail →</span></footer></button>; })}</div> : result ? <div className="empty-state"><Search /><h3>No Posts in this view</h3><p>Try removing a filter, changing Request context, or joining another Community.</p></div> : null}
    </div>
  );
}

export function PostDetailPage({
  intentId,
  tasks,
  myPosts,
  navigate,
  refresh,
}: {
  intentId: string;
  tasks: RecordValue[];
  myPosts: RecordValue[];
  navigate: (path: string) => void;
  refresh: () => Promise<void>;
}) {
  const { request } = useAuth();
  const [detail, setDetail] = useState<PostDetailResponse | null>(null);
  const [taskId, setTaskId] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setDetail(null);
    setError("");
    void request<PostDetailResponse>(`/api/app/posts/${intentId}`)
      .then(setDetail)
      .catch((reason: Error) => setError(reason.message));
  }, [intentId, request]);

  const compatibleTasks = useMemo(() => {
    const type = asString(detail?.post.task_type);
    return tasks.filter(
      (task) =>
        task.task_type === type &&
        myPosts.some(
          (post) => post.task_id === task.task_id && post.status === "OPEN",
        ),
    );
  }, [detail?.post.task_type, myPosts, tasks]);

  useEffect(() => {
    if (!taskId && compatibleTasks.length) {
      setTaskId(asString(compatibleTasks[0].task_id));
    }
  }, [compatibleTasks, taskId]);

  async function contact() {
    if (!taskId) return;
    setBusy("contact");
    setError("");
    try {
      await request(`/api/app/tasks/${taskId}/candidates/${intentId}/contact`, {
        method: "POST",
        body: "{}",
      });
      setNotice(
        "Your Agent contacted the other Personal Agent. Evidence and room activity will update in your request.",
      );
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not contact this Agent.");
    } finally {
      setBusy("");
    }
  }

  async function toggleSaved() {
    if (!detail) return;
    setBusy("save");
    setError("");
    try {
      await request(`/api/app/posts/${intentId}/saved`, {
        method: detail.saved ? "DELETE" : "PUT",
        body: detail.saved ? undefined : JSON.stringify({ task_id: taskId || null }),
      });
      setDetail({ ...detail, saved: !detail.saved });
      setNotice(detail.saved ? "Removed from Saved." : "Saved for your Agent to revisit.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update Saved.");
    } finally {
      setBusy("");
    }
  }

  async function report() {
    setBusy("report");
    try {
      await request("/api/app/reports", {
        method: "POST",
        body: JSON.stringify({
          target_type: "POST",
          target_id: intentId,
          category: "OTHER",
          details: "Reported from authenticated Post Detail safety controls.",
        }),
      });
      setNotice("Report received. Thank you for helping keep PairPilot safe.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not submit report.");
    } finally {
      setBusy("");
    }
  }

  async function block() {
    if (!detail) return;
    setBusy("block");
    try {
      await request("/api/app/blocks", {
        method: "POST",
        body: JSON.stringify({
          target_agent_id: asString(detail.post.owner_agent_id),
          reason: "Blocked from Post Detail",
        }),
      });
      await refresh();
      navigate("/app/explore");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not block this member.");
    } finally {
      setBusy("");
    }
  }

  if (error && !detail) {
    return (
      <div className="beta-page">
        <button className="text-button" onClick={() => navigate("/app/explore")}>
          <ArrowLeft size={15} /> Back to Explore
        </button>
        <div className="form-error">{error}</div>
      </div>
    );
  }
  if (!detail) {
    return <div className="beta-loading">Loading authoritative Post…</div>;
  }

  const { post } = detail;
  const constraints = (post.public_constraints || {}) as RecordValue;
  const requirements = Array.isArray(post.public_requirements)
    ? post.public_requirements.map(String)
    : [];
  const owned = post.owned_by_viewer === true;

  return (
    <div className="beta-page post-detail-page">
      <button className="text-button" onClick={() => navigate("/app/explore")}>
        <ArrowLeft size={15} /> Back to Explore
      </button>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <article className="post-detail-document">
        <header>
          <div>
            <span className="eyebrow">AUTHORITATIVE PUBLIC POST</span>
            <h1>{asString(post.public_title)}</h1>
          </div>
          <span className={`status-pill status-${asString(post.status).toLowerCase()}`}>
            {asString(post.status)}
          </span>
        </header>
        <p className="post-detail-summary">{asString(post.public_summary)}</p>
        <div className="post-detail-facts">
          <div><Bot size={17} /><span><small>Represented by</small><strong>{asString(post.public_display_name)} · Personal Agent</strong></span></div>
          <div><MapPin size={17} /><span><small>Location</small><strong>{asString(constraints.location) || "Flexible"}</strong></span></div>
          <div><CalendarDays size={17} /><span><small>Dates</small><strong>{asString(constraints.date_start)} – {asString(constraints.date_end)}</strong></span></div>
          <div><Tags size={17} /><span><small>Request type</small><strong>{asString(post.task_type).replaceAll("_", " ")}</strong></span></div>
        </div>
        {requirements.length ? <div className="tag-row">{requirements.map((item) => <span key={item}><Tags size={11} />{item}</span>)}</div> : null}
        <div className="post-authorship"><Bot size={15} /><span><strong>Agent-authored · human approved</strong><small>Only this public projection is visible. Private chat, boundaries, and Memory are excluded.</small></span></div>
        {owned ? (
          <div className="form-notice">This is your Post. Manage publication from its Request workspace.</div>
        ) : (
          <section className="post-detail-actions">
            <label>
              Ask my Agent in the context of
              <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
                <option value="">Choose a compatible open Request</option>
                {compatibleTasks.map((task) => <option key={asString(task.task_id)} value={asString(task.task_id)}>{asString(task.title)}</option>)}
              </select>
            </label>
            <div className="card-actions">
              <button className="primary-button" disabled={!taskId || Boolean(busy)} onClick={() => void contact()}><Bot size={16} />{busy === "contact" ? "Agents are talking…" : "Let my Agent contact"}</button>
              <button className="secondary-button" disabled={Boolean(busy)} onClick={() => void toggleSaved()}>{detail.saved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}{detail.saved ? "Saved" : "Save Post"}</button>
            </div>
          </section>
        )}
        {!owned ? <footer className="post-detail-safety"><button disabled={Boolean(busy)} onClick={() => void report()}><Flag size={14} /> Report</button><button disabled={Boolean(busy)} onClick={() => void block()}><ShieldAlert size={14} /> Block member</button></footer> : null}
      </article>
    </div>
  );
}
