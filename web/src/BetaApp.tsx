import {
  Bell,
  Bot,
  Building2,
  CheckCircle2,
  Compass,
  Download,
  GitBranch,
  LayoutList,
  LoaderCircle,
  LogOut,
  MemoryStick,
  MessageSquareMore,
  Plus,
  Settings,
  ShieldCheck,
  Trash2,
  UsersRound,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useAuth } from "./auth";
import { PersonalAgentChat } from "./components/PersonalAgentChat";
import {
  MarketplaceExplorePage,
  PostDetailPage,
} from "./pages/MarketplacePages";
import { CommunityDetailPage, CommunityListPage } from "./pages/CommunityPages";
import { ConnectionDetailPage, ConnectionsPage } from "./pages/ConnectionPages";
import { MatchDetailPage, MatchesPage } from "./pages/MatchPages";
import {
  MemoryDetailPage,
  MemoryPage as V2MemoryPage,
} from "./pages/MemoryPages";
import {
  AutonomyCenterPage,
  DecisionInboxPage,
  NotificationsPage as V2NotificationsPage,
} from "./pages/ProductGluePages";
import { OperationsPage } from "./pages/OperationsPage";
import { RequestWorkspaceV2Page } from "./pages/RequestWorkspaceV2Page";
import { RoomDetailPage, RoomsPage } from "./pages/RoomPages";
import { useRouter } from "./router";

type RecordValue = Record<string, unknown>;
interface BetaBootstrap {
  profile: RecordValue;
  personalAgent: RecordValue;
  privacy: RecordValue;
  autonomy: RecordValue;
  quota: RecordValue;
  tasks: RecordValue[];
  conversations: RecordValue[];
  conversationMessages: RecordValue[];
  presentationDirectives: RecordValue[];
  decisions: RecordValue[];
  rooms: RecordValue[];
  matches: RecordValue[];
  myPosts: RecordValue[];
  explorePosts: RecordValue[];
  relationships: RecordValue[];
  memories: RecordValue[];
  communities: RecordValue[];
  communityMemberships: RecordValue[];
  notifications: RecordValue[];
  candidateAssessments: RecordValue[];
  candidateRankEvents: RecordValue[];
  contactCards: RecordValue[];
  outcomes: RecordValue[];
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const asNumber = (value: unknown) => (typeof value === "number" ? value : 0);

function Loading() {
  return (
    <div className="beta-loading">
      <LoaderCircle className="spin" />
      <span>Loading your private workspace…</span>
    </div>
  );
}

function BetaShell({
  data,
  path,
  navigate,
  onSignOut,
  children,
}: {
  data: BetaBootstrap;
  path: string;
  navigate: (path: string) => void;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  const openDecisions = data.decisions.filter(
    (item) => item.status === "OPEN",
  ).length;
  const unreadNotifications = data.notifications.filter(
    (item) => item.status === "UNREAD",
  ).length;
  const links = [
    ["/app/agent", Bot, "My Agent"],
    ["/app/decisions", CheckCircle2, "Decisions"],
    ["/app/requests", LayoutList, "Requests"],
    ["/app/explore", Compass, "Explore"],
    ["/app/communities", Building2, "Communities"],
    ["/app/rooms", MessageSquareMore, "Rooms"],
    ["/app/matches", CheckCircle2, "Matches"],
    ["/app/connections", UsersRound, "Connections"],
    ["/app/memory", MemoryStick, "Memory"],
    ["/app/notifications", Bell, "Notifications"],
    ["/app/settings", Settings, "Settings"],
  ] as const;
  const visibleLinks = data.profile.admin
    ? [...links, ["/app/admin", ShieldCheck, "Admin"] as const]
    : links;
  return (
    <div className="beta-shell">
      <aside className="beta-sidebar">
        <button
          className="beta-brand inverse"
          onClick={() => navigate("/app/agent")}
        >
          <span>
            <GitBranch size={19} />
          </span>
          PairPilot
        </button>
        <div className="owned-agent">
          <div className="agent-avatar">
            <Bot size={18} />
          </div>
          <span>
            <strong>
              {asString(data.personalAgent.display_name) || "Personal Agent"}
            </strong>
            <small>User-owned · private</small>
          </span>
          <i />
        </div>
        <button className="new-task" onClick={() => navigate("/app/agent")}>
          <Plus size={16} /> New request
        </button>
        <nav>
          {visibleLinks.map(([href, Icon, label]) => (
            <button
              key={href}
              className={path.startsWith(href) ? "active" : ""}
              onClick={() => navigate(href)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === "Decisions" && openDecisions ? (
                <b>{openDecisions}</b>
              ) : null}
              {label === "Notifications" && unreadNotifications ? (
                <b>{unreadNotifications}</b>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="beta-sidebar-footer">
          <span>
            <ShieldCheck size={15} /> Dual-human approval
          </span>
          <button onClick={onSignOut}>
            <LogOut size={15} /> Sign out
          </button>
        </div>
      </aside>
      <main className="beta-main">
        {!online ? (
          <div className="offline-banner" role="status">
            You are offline. Existing content remains visible; sending and state
            changes will be available after reconnection.
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}

function Onboarding({ onDone }: { onDone: () => Promise<void> }) {
  const { request } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [adult, setAdult] = useState(false);
  const [notifications, setNotifications] = useState("IN_APP");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request("/api/app/onboarding", {
        method: "PUT",
        body: JSON.stringify({
          display_name: name,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
          general_location: location,
          language: navigator.language || "en",
          adult_confirmed: adult,
          public_profile_visible: true,
          default_autonomy_mode: "COPILOT",
          public_sharing_policy: "Ask me before publishing any public post.",
          agent_sharing_policy: "Share only the minimum public task evidence.",
          always_ask_policy:
            "Always ask before publishing, identity disclosure, payment, booking, or commitment.",
          community_ids: ["community_icml_seoul_2026"],
          default_public_visibility: "COMMUNITY",
          default_agent_visibility: "MINIMUM_NECESSARY",
          notification_preference: notifications,
        }),
      });
      await onDone();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save onboarding.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="onboarding-page">
      <div className="onboarding-card">
        <div className="auth-icon">
          <Bot />
        </div>
        <span className="eyebrow">SET UP YOUR PERSONAL AGENT</span>
        <h1>Give your Agent the rules of the road.</h1>
        <p>
          Your account, private memory, decisions, and relationships are
          isolated from every other user.
        </p>
        <form onSubmit={submit}>
          <label>
            Display name
            <input
              value={name}
              maxLength={60}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label>
            General location
            <input
              value={location}
              maxLength={120}
              placeholder="e.g. Shanghai, China"
              onChange={(event) => setLocation(event.target.value)}
              required
            />
          </label>
          <label>
            Starting community
            <input value="ICML Seoul 2026" disabled />
          </label>
          <label>
            Notifications
            <select
              value={notifications}
              onChange={(event) => setNotifications(event.target.value)}
            >
              <option value="IN_APP">In-app only</option>
              <option value="IN_APP_AND_EMAIL">In-app and email</option>
              <option value="NONE">None</option>
            </select>
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={adult}
              onChange={(event) => setAdult(event.target.checked)}
              required
            />{" "}
            I confirm I’m 18 or older and understand PairPilot does not verify
            identity or guarantee safety.
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          <button className="primary-button full" disabled={busy}>
            {busy ? "Creating your Agent…" : "Enter my workspace"}
          </button>
        </form>
      </div>
    </div>
  );
}

function AgentHome({
  data,
  refresh,
  navigate,
}: {
  data: BetaBootstrap;
  refresh: () => Promise<void>;
  navigate: (path: string) => void;
}) {
  const recent = [...data.tasks]
    .sort((a, b) =>
      asString(b.updated_at).localeCompare(asString(a.updated_at)),
    )
    .slice(0, 3);
  const conversation = data.conversations.find(
    (item) => item.kind === "GLOBAL_PERSONAL_AGENT",
  );
  const messages = data.conversationMessages.filter(
    (item) => item.conversation_id === conversation?.conversation_id,
  );
  return (
    <div className="beta-page agent-home real-agent-home">
      <header>
        <span className="eyebrow">YOUR ONE PERSISTENT PERSONAL AGENT</span>
        <h1>Talk to your Agent.</h1>
        <p>
          Everything stays in this conversation: clarifying questions, post
          review, Agent-to-Agent coordination, ranked candidates, and match
          updates.
        </p>
      </header>
      <PersonalAgentChat
        conversation={conversation}
        messages={messages}
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
      <section className="beta-section">
        <div className="section-heading">
          <h2>Recent requests</h2>
          <button
            className="text-button"
            onClick={() => navigate("/app/requests")}
          >
            View all
          </button>
        </div>
        {recent.length ? (
          <div className="request-grid">
            {recent.map((task) => (
              <RequestCard
                key={asString(task.task_id)}
                task={task}
                onOpen={() =>
                  navigate(`/app/requests/${asString(task.task_id)}`)
                }
              />
            ))}
          </div>
        ) : (
          <Empty
            icon={<Bot />}
            title="No request workspace yet"
            body="Start with a normal message above. Your Agent will create one when it has enough information."
          />
        )}
      </section>
    </div>
  );
}

function RequestCard({
  task,
  onOpen,
}: {
  task: RecordValue;
  onOpen: () => void;
}) {
  return (
    <button className="request-card" onClick={onOpen}>
      <div>
        <span
          className={`status-pill status-${asString(task.status).toLowerCase()}`}
        >
          {asString(task.status)}
        </span>
        <small>{asString(task.task_type).replaceAll("_", " ")}</small>
      </div>
      <h3>{asString(task.title)}</h3>
      <p>{asString(task.goal)}</p>
      <span>Open request →</span>
    </button>
  );
}
function Empty({
  icon,
  title,
  body,
}: {
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="empty-state">
      <div>{icon}</div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function Requests({
  data,
  navigate,
}: {
  data: BetaBootstrap;
  navigate: (path: string) => void;
}) {
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="REQUEST CONTEXTS"
        title="Requests"
        subtitle="Requests organize work, but your conversation with your Personal Agent always stays in one continuous thread."
      />
      {data.tasks.length ? (
        <div className="request-grid">
          {data.tasks.map((task) => (
            <RequestCard
              key={asString(task.task_id)}
              task={task}
              onOpen={() => navigate(`/app/requests/${asString(task.task_id)}`)}
            />
          ))}
        </div>
      ) : (
        <Empty
          icon={<LayoutList />}
          title="No requests yet"
          body="Tell your Agent what you need to begin."
        />
      )}
    </div>
  );
}

export function MemoryPage({
  data,
  refresh,
}: {
  data: BetaBootstrap;
  refresh: () => Promise<void>;
}) {
  const { request } = useAuth();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function act(memory: RecordValue, action: string) {
    const memoryId = asString(memory.memory_id);
    setBusy(memoryId);
    setError("");
    try {
      await request(`/api/app/memories/${memoryId}/actions`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setNotice(
        action === "CONFIRM"
          ? "Memory confirmed. Your Agent may now use it within its stated scope."
          : "Memory preference updated.",
      );
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not update Memory.",
      );
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="PRIVATE TO YOU"
        title="Memory"
        subtitle="Proposed memories are inert until you confirm them. You can stop, archive, reject, or delete use at any time."
      />
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      {data.memories.length ? (
        <div className="request-grid">
          {data.memories.map((memory) => {
            const memoryId = asString(memory.memory_id);
            const status =
              asString(memory.status) ||
              asString(memory.confirmation_status) ||
              "PROPOSED";
            const disabled = busy === memoryId;
            return (
              <article className="published-card" key={memoryId}>
                <MemoryStick />
                <span className="status-pill">{status}</span>
                <h2>{asString(memory.title) || "Agent memory"}</h2>
                <p>{asString(memory.content) || "Content deleted"}</p>
                <small>Scope: {asString(memory.scope) || "GLOBAL"}</small>
                <div className="card-actions">
                  {status === "PROPOSED" || status === "REVIEWABLE" ? (
                    <>
                      <button
                        className="primary-button"
                        disabled={disabled}
                        onClick={() => void act(memory, "CONFIRM")}
                      >
                        Confirm
                      </button>
                      <button
                        className="secondary-button"
                        disabled={disabled}
                        onClick={() => void act(memory, "REJECT")}
                      >
                        Reject
                      </button>
                    </>
                  ) : null}
                  {status === "CONFIRMED" ? (
                    <>
                      <button
                        className="secondary-button"
                        disabled={disabled}
                        onClick={() => void act(memory, "STOP_USING")}
                      >
                        Stop using
                      </button>
                      <button
                        className="secondary-button"
                        disabled={disabled}
                        onClick={() => void act(memory, "ARCHIVE")}
                      >
                        Archive
                      </button>
                    </>
                  ) : null}
                  <button
                    className="danger-button"
                    disabled={disabled}
                    onClick={() => void act(memory, "DELETE")}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <Empty
          icon={<MemoryStick />}
          title="No retained memory yet"
          body="Your Agent may propose useful memories after completed work; proposals remain inert until you confirm them."
        />
      )}
    </div>
  );
}

export function Notifications({ data }: { data: BetaBootstrap }) {
  const items = [...data.notifications].sort((a, b) =>
    asString(b.created_at).localeCompare(asString(a.created_at)),
  );
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="AGENT ACTIVITY"
        title="Notifications"
        subtitle="Candidate changes, approvals, match updates, and monitoring results appear here."
      />
      {items.length ? (
        <div className="notification-list">
          {items.map((item) => (
            <article
              className="published-card"
              key={asString(item.notification_id)}
            >
              <Bell />
              <span className="status-pill">{asString(item.status)}</span>
              <h2>{asString(item.title)}</h2>
              <p>{asString(item.body)}</p>
              <small>{asString(item.created_at)}</small>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          icon={<Bell />}
          title="Nothing new"
          body="Your Agent will notify you when a candidate rank changes or a decision needs you."
        />
      )}
    </div>
  );
}

export function MatchCard({
  match,
  data,
  refresh,
}: {
  match: RecordValue;
  data: BetaBootstrap;
  refresh: () => Promise<void>;
}) {
  const { request } = useAuth();
  const { navigate } = useRouter();
  const matchId = asString(match.match_id);
  const [cards, setCards] = useState<RecordValue[]>([]);
  const [publicEmail, setPublicEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [wechat, setWechat] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const outcome = data.outcomes.find((item) => item.match_id === matchId);
  const loadCards = useCallback(
    () =>
      request<{ contactCards: RecordValue[] }>(
        `/api/app/matches/${matchId}/contacts`,
      ).then((payload) => setCards(payload.contactCards)),
    [matchId, request],
  );
  useEffect(() => {
    void loadCards();
  }, [loadCards]);
  async function offer(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request(`/api/app/matches/${matchId}/contacts/mine`, {
        method: "PUT",
        body: JSON.stringify({
          public_email: publicEmail || null,
          phone: phone || null,
          whatsapp: null,
          telegram: null,
          wechat: wechat || null,
          linkedin: linkedin || null,
          other_handle: null,
        }),
      });
      setNotice(
        "Only the fields you entered are now visible to this matched person.",
      );
      await loadCards();
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not offer contact card.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function revoke() {
    setBusy(true);
    try {
      await request(`/api/app/matches/${matchId}/contacts/mine`, {
        method: "DELETE",
      });
      setNotice("Your offered contact fields were revoked.");
      await loadCards();
      await refresh();
    } finally {
      setBusy(false);
    }
  }
  async function outcomeCheck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await request(`/api/app/matches/${matchId}/outcome`, {
        method: "POST",
        body: JSON.stringify({
          did_plan_happen: form.get("happened") === "yes",
          would_coordinate_again: form.get("again") === "yes",
          agreed_term_inaccurate: form.get("inaccurate") === "yes",
          optional_feedback: asString(form.get("feedback")) || null,
        }),
      });
      setNotice(
        "Private outcome saved. Relationship evidence was updated without publishing your feedback.",
      );
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save outcome.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="match-card">
      <header>
        <CheckCircle2 />
        <div>
          <span className="status-pill">CONFIRMED</span>
          <h2>Confirmed match</h2>
          <p>Both people approved proposal {asString(match.proposal_id)}.</p>
        </div>
        <button
          className="secondary-button"
          onClick={() => navigate(`/app/rooms/${asString(match.room_id)}`)}
        >
          Open shared room
        </button>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <section>
        <h3>Match-scoped contact cards</h3>
        <p>
          Login email is never shared. Each person chooses individual contact
          fields.
        </p>
        {cards.length ? (
          <div className="contact-card-list">
            {cards.map((card) => (
              <div key={asString(card.contact_card_id)}>
                <strong>{asString(card.display_name)}</strong>
                {Object.entries((card.fields || {}) as RecordValue).map(
                  ([key, value]) => (
                    <span key={key}>
                      {key.replaceAll("_", " ")}: {asString(value)}
                    </span>
                  ),
                )}
              </div>
            ))}
          </div>
        ) : (
          <small>No contact details have been offered.</small>
        )}
        <form className="contact-form" onSubmit={offer}>
          <input
            aria-label="Public contact email"
            placeholder="Public email (optional)"
            value={publicEmail}
            onChange={(event) => setPublicEmail(event.target.value)}
          />
          <input
            aria-label="Contact phone"
            placeholder="Phone (optional)"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
          <input
            aria-label="WeChat"
            placeholder="WeChat (optional)"
            value={wechat}
            onChange={(event) => setWechat(event.target.value)}
          />
          <input
            aria-label="LinkedIn"
            placeholder="LinkedIn (optional)"
            value={linkedin}
            onChange={(event) => setLinkedin(event.target.value)}
          />
          <button className="primary-button" disabled={busy}>
            Offer selected fields
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => void revoke()}
          >
            Revoke mine
          </button>
        </form>
      </section>
      <section>
        <h3>Private outcome check-in</h3>
        {outcome ? (
          <p className="form-notice">
            Outcome recorded. Your private feedback is not shown to the other
            person.
          </p>
        ) : (
          <form className="outcome-form" onSubmit={outcomeCheck}>
            <label>
              Did the plan happen?
              <select name="happened">
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
            <label>
              Would you coordinate again?
              <select name="again">
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
            <label>
              Was an agreed term inaccurate?
              <select name="inaccurate">
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </label>
            <label>
              Optional private feedback
              <textarea name="feedback" maxLength={1000} />
            </label>
            <button className="primary-button" disabled={busy}>
              Save private outcome
            </button>
          </form>
        )}
      </section>
    </article>
  );
}

export function Matches({
  data,
  refresh,
}: {
  data: BetaBootstrap;
  refresh: () => Promise<void>;
}) {
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="ATOMIC DUAL APPROVAL"
        title="Matches"
        subtitle="A match exists only after both Agents and both people approved the same proposal version."
      />
      {data.matches.length ? (
        <div className="match-list">
          {data.matches.map((match) => (
            <MatchCard
              key={asString(match.match_id)}
              match={match}
              data={data}
              refresh={refresh}
            />
          ))}
        </div>
      ) : (
        <Empty
          icon={<CheckCircle2 />}
          title="No matches yet"
          body="One person’s approval is never enough to create a match."
        />
      )}
    </div>
  );
}

export function NetworkPage({ data }: { data: BetaBootstrap }) {
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="AUTHORITATIVE OUTCOMES ONLY"
        title="Network"
        subtitle="Contextual relationship evidence comes from committed matches and private owner outcomes—not peer Agent claims."
      />
      {data.relationships.length ? (
        <div className="request-grid">
          {data.relationships.map((relationship) => {
            const candidate = data.candidateAssessments.find(
              (item) => item.proposal_id === relationship.match_id,
            );
            const peerName =
              asString(relationship.peer_display_name) ||
              asString(candidate?.candidate_display_name) ||
              "Matched connection";
            return (
              <article
                className="published-card"
                key={asString(relationship.relationship_id)}
              >
                <UsersRound />
                <span className="status-pill">
                  {asString(relationship.relation_type)}
                </span>
                <h2>{peerName}</h2>
                <p>
                  {asString(relationship.introduction_path).replaceAll(
                    "_",
                    " ",
                  )}{" "}
                  ·{" "}
                  {(Array.isArray(relationship.task_type_compatibility)
                    ? relationship.task_type_compatibility
                    : []
                  ).join(", ")}
                </p>
                <dl>
                  <dt>Committed plans</dt>
                  <dd>{asNumber(relationship.plans_committed)}</dd>
                  <dt>Reported successful</dt>
                  <dd>{asNumber(relationship.successful_plans)}</dd>
                  <dt>Would coordinate again</dt>
                  <dd>{asNumber(relationship.would_coordinate_again_yes)}</dd>
                  <dt>Last interaction</dt>
                  <dd>
                    {asString(relationship.last_interaction_at) ||
                      asString(relationship.updated_at)}
                  </dd>
                </dl>
                <small>
                  Provenance: atomic Match and owner-submitted outcome events.
                </small>
              </article>
            );
          })}
        </div>
      ) : (
        <Empty
          icon={<UsersRound />}
          title="Your network starts with a real match"
          body="Public posts and Agent claims alone never create relationship evidence."
        />
      )}
    </div>
  );
}

function SettingsPage({
  data,
  onSignOut,
  navigate,
}: {
  data: BetaBootstrap;
  onSignOut: () => void;
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [notice, setNotice] = useState("");
  const [confirmDelete, setConfirmDelete] = useState("");
  const [notificationPreference, setNotificationPreference] = useState(
    asString(data.profile.notification_preference) || "IN_APP",
  );
  const [autonomyMode, setAutonomyMode] = useState(
    asString(data.autonomy.default_mode) || "COPILOT",
  );
  async function downloadExport() {
    const payload = await request<RecordValue>("/api/app/account/export");
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `pairpilot-account-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    setNotice("Account export downloaded to this device.");
  }
  async function deleteAccount() {
    if (confirmDelete !== "DELETE MY PAIRPILOT ACCOUNT") {
      setNotice("Type the exact confirmation phrase first.");
      return;
    }
    await request("/api/app/account/delete", {
      method: "POST",
      body: JSON.stringify({ confirmation: confirmDelete }),
    });
    setNotice(
      "Deletion is scheduled. Active posts and negotiations are closed.",
    );
    onSignOut();
  }
  async function saveSettings() {
    await request("/api/app/settings", {
      method: "PUT",
      body: JSON.stringify({
        display_name: asString(data.profile.display_name),
        default_autonomy_mode: autonomyMode,
        public_sharing_policy:
          autonomyMode === "AGENT"
            ? "My Agent may publish ordinary posts after collecting enough information."
            : "Ask me before publishing each public post.",
        agent_sharing_policy: asString(data.privacy.agent_sharing_policy),
        notification_preference: notificationPreference,
      }),
    });
    setNotice("Agent access and notification preferences saved.");
  }
  return (
    <div className="beta-page">
      <PageTitle
        eyebrow="ACCOUNT & AUTHORITY"
        title="Settings"
        subtitle="Choose how much routine work your Agent can complete without interrupting you."
      />
      {notice ? <div className="form-notice">{notice}</div> : null}
      <div className="settings-grid">
        <section>
          <h2>Account</h2>
          <dl>
            <dt>Display name</dt>
            <dd>{asString(data.profile.display_name)}</dd>
            <dt>Email</dt>
            <dd>{asString(data.profile.email)}</dd>
            <dt>Email verified</dt>
            <dd>{data.profile.email_verified ? "Yes" : "No"}</dd>
          </dl>
        </section>
        <section>
          <h2>Agent access</h2>
          <label>
            Default mode
            <select
              aria-label="Agent access mode"
              value={autonomyMode}
              onChange={(event) => setAutonomyMode(event.target.value)}
            >
              <option value="COPILOT">
                Copilot — approve each public post
              </option>
              <option value="AGENT">
                Full access — publish routine posts automatically
              </option>
              <option value="HUMAN">
                Draft only — I perform actions myself
              </option>
            </select>
          </label>
          <p>
            Even with Full access, your Agent must always ask before sharing
            identity/contact details, paying, booking, or committing you to a
            plan.
          </p>
          <button
            className="secondary-button"
            onClick={() => navigate("/app/settings/autonomy")}
          >
            Open action-specific Autonomy Center
          </button>
        </section>
        <section>
          <h2>Privacy</h2>
          <p>{asString(data.privacy.agent_sharing_policy)}</p>
          <p>
            {autonomyMode === "AGENT"
              ? "Routine public posts may be published after the Agent has enough information."
              : "Each public post requires your approval."}
          </p>
        </section>
        <section>
          <h2>Usage boundaries</h2>
          <p>
            {asNumber(data.quota.active_task_limit)} active requests ·{" "}
            {asNumber(data.quota.concurrent_negotiations_per_task)} concurrent
            negotiations per request.
          </p>
        </section>
        <section>
          <h2>Notifications</h2>
          <select
            value={notificationPreference}
            onChange={(event) => setNotificationPreference(event.target.value)}
          >
            <option value="IN_APP">In-app only</option>
            <option value="IN_APP_AND_EMAIL">In-app and email</option>
            <option value="NONE">None</option>
          </select>
          <button
            className="secondary-button"
            onClick={() => void saveSettings()}
          >
            Save settings
          </button>
        </section>
        <section>
          <h2>Safety guidance</h2>
          <p>
            PairPilot does not verify identity or guarantee safety. Meet in
            public, keep room numbers and precise real-time location private,
            and use Block or Report whenever needed.
          </p>
        </section>
      </div>
      <div className="account-actions">
        <button
          className="secondary-button"
          onClick={() => void downloadExport()}
        >
          <Download size={16} /> Download my data
        </button>
        <button className="secondary-button" onClick={onSignOut}>
          <LogOut size={16} /> Sign out of this device
        </button>
      </div>
      <section className="danger-zone">
        <h2>Delete account</h2>
        <p>
          This immediately removes you from discovery, closes active posts,
          cancels uncommitted negotiations, releases holds, revokes room access
          and provider sessions, then schedules private-data erasure.
        </p>
        <input
          aria-label="Account deletion confirmation"
          value={confirmDelete}
          onChange={(event) => setConfirmDelete(event.target.value)}
          placeholder="DELETE MY PAIRPILOT ACCOUNT"
        />
        <button
          onClick={() => void deleteAccount()}
          disabled={confirmDelete !== "DELETE MY PAIRPILOT ACCOUNT"}
        >
          <Trash2 size={15} /> Schedule account deletion
        </button>
      </section>
    </div>
  );
}

function PageTitle({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <header className="page-title">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
}

export function BetaApp() {
  const { request, user, loading, signOutUser } = useAuth();
  const { path, navigate } = useRouter();
  const [data, setData] = useState<BetaBootstrap | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const next = await request<BetaBootstrap>("/api/app/bootstrap");
    setData(next);
  }, [request]);
  useEffect(() => {
    if (!loading && !user) navigate("/sign-in", true);
    else if (user && !user.emailVerified) navigate("/verify-email", true);
  }, [loading, navigate, user]);
  useEffect(() => {
    if (user?.emailVerified) {
      void request("/api/app/provision", { method: "POST", body: "{}" })
        .then(refresh)
        .catch((reason: Error) => setError(reason.message));
    }
  }, [refresh, request, user]);
  const signOutNow = useCallback(() => {
    void signOutUser().then(() => {
      setData(null);
      sessionStorage.clear();
      navigate("/sign-in", true);
    });
  }, [navigate, signOutUser]);
  const taskId = path.startsWith("/app/requests/") ? path.split("/")[3] : "";
  const roomId = path.startsWith("/app/rooms/") ? path.split("/")[3] : "";
  const postId = path.startsWith("/app/posts/") ? path.split("/")[3] : "";
  const communityId = path.startsWith("/app/communities/")
    ? path.split("/")[3]
    : "";
  const matchId = path.startsWith("/app/matches/") ? path.split("/")[3] : "";
  const connectionId = path.startsWith("/app/connections/")
    ? path.split("/")[3]
    : "";
  const memoryId = path.startsWith("/app/memory/") ? path.split("/")[3] : "";
  let page: ReactNode = <Loading />;
  if (data) {
    if (data.profile.onboarding_status !== "COMPLETED")
      page = <Onboarding onDone={refresh} />;
    else if (path === "/app/agent" || path === "/onboarding")
      page = <AgentHome data={data} refresh={refresh} navigate={navigate} />;
    else if (path === "/app/requests")
      page = <Requests data={data} navigate={navigate} />;
    else if (taskId)
      page = (
        <RequestWorkspaceV2Page
          taskId={taskId}
          data={data}
          refresh={refresh}
          navigate={navigate}
        />
      );
    else if (path === "/app/explore")
      page = (
        <MarketplaceExplorePage
          tasks={data.tasks}
          myPosts={data.myPosts}
          communities={data.communities}
          navigate={navigate}
        />
      );
    else if (postId)
      page = (
        <PostDetailPage
          intentId={postId}
          tasks={data.tasks}
          myPosts={data.myPosts}
          navigate={navigate}
          refresh={refresh}
        />
      );
    else if (path === "/app/communities")
      page = (
        <CommunityListPage data={data} refresh={refresh} navigate={navigate} />
      );
    else if (communityId)
      page = (
        <CommunityDetailPage
          communityId={communityId}
          refresh={refresh}
          navigate={navigate}
        />
      );
    else if (path === "/app/rooms") page = <RoomsPage navigate={navigate} />;
    else if (roomId)
      page = (
        <RoomDetailPage
          roomId={roomId}
          navigate={navigate}
          data={data}
          refresh={refresh}
        />
      );
    else if (path === "/app/matches")
      page = <MatchesPage navigate={navigate} />;
    else if (matchId)
      page = <MatchDetailPage matchId={matchId} navigate={navigate} />;
    else if (path === "/app/connections" || path === "/app/network")
      page = <ConnectionsPage navigate={navigate} />;
    else if (connectionId)
      page = (
        <ConnectionDetailPage connectionId={connectionId} navigate={navigate} />
      );
    else if (path === "/app/memory")
      page = <V2MemoryPage navigate={navigate} />;
    else if (memoryId)
      page = <MemoryDetailPage memoryId={memoryId} navigate={navigate} />;
    else if (path === "/app/decisions")
      page = <DecisionInboxPage navigate={navigate} />;
    else if (path === "/app/notifications")
      page = <V2NotificationsPage navigate={navigate} />;
    else if (path === "/app/admin") page = <OperationsPage />;
    else if (path === "/app/settings/autonomy")
      page = <AutonomyCenterPage tasks={data.tasks} />;
    else if (path === "/app/settings")
      page = (
        <SettingsPage data={data} onSignOut={signOutNow} navigate={navigate} />
      );
    else page = <AgentHome data={data} refresh={refresh} navigate={navigate} />;
  }
  if (loading) return <Loading />;
  if (!user || !user.emailVerified) return <Loading />;
  if (data?.profile.onboarding_status !== "COMPLETED")
    return (
      <>
        {error ? (
          <div className="form-error floating-error">{error}</div>
        ) : null}
        {page}
      </>
    );
  return (
    <BetaShell
      data={data}
      path={path}
      navigate={navigate}
      onSignOut={signOutNow}
    >
      {error ? <div className="form-error">{error}</div> : null}
      {page}
    </BetaShell>
  );
}
