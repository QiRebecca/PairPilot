import { Bot, Building2, CalendarDays, Flag, MapPin, MessageCircle, ShieldCheck, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../auth";

type RecordValue = Record<string, unknown>;

interface CommunityBootstrap {
  communities: RecordValue[];
  communityMemberships: RecordValue[];
}

interface CommunityDetail {
  community: RecordValue;
  viewer: { joined: boolean; role?: string; can_moderate: boolean };
  counts: { members: number; active_posts: number; active_plans: number };
  moderators: string[];
  open_requests: Record<string, RecordValue[]>;
  members: RecordValue[];
  plans_and_rooms: RecordValue[];
}

const asString = (value: unknown) => typeof value === "string" ? value : "";
const tabs = ["Overview", "Open Requests", "Members & Agents", "Plans & Rooms", "Rules"] as const;
const requestLabels: Record<string, string> = {
  ROOM_SHARE: "Room share",
  MEAL_COMPANION: "Meals",
  COFFEE_CHAT: "Coffee chats",
  EVENT_BUDDY: "Event buddies",
  HACKATHON_TEAMMATE: "Teams",
};

export function CommunityListPage({ data, refresh, navigate }: {
  data: CommunityBootstrap;
  refresh: () => Promise<void>;
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const memberships = useMemo(() => new Map(data.communityMemberships.map((item) => [asString(item.community_id), item])), [data.communityMemberships]);

  async function changeMembership(communityId: string, joined: boolean) {
    setBusy(communityId); setError(""); setNotice("");
    try {
      const response = await request<{ membership: RecordValue }>(`/api/app/communities/${communityId}/${joined ? "leave" : "join"}`, { method: "POST", body: joined ? undefined : "{}" });
      const status = asString(response.membership.status);
      setNotice(joined ? "You left the Community. Its open Posts were paused." : status === "PENDING" ? "Membership request sent for moderator approval." : "Community joined. Your Agent can now discover and publish within it.");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update membership."); }
    finally { setBusy(""); }
  }

  return <div className="beta-page"><header className="page-title"><span className="eyebrow">LIQUIDITY & TRUST LAYERS</span><h1>Communities</h1><p>Operational spaces where membership controls what your Agent may publish, discover, and coordinate.</p></header>{notice ? <div className="form-notice">{notice}</div> : null}{error ? <div className="form-error">{error}</div> : null}<div className="community-grid">{data.communities.map((community) => { const id = asString(community.community_id); const membership = memberships.get(id); const joined = membership?.status === "ACTIVE"; return <article className="community-list-card" key={id}><div className="community-card-icon"><Building2 size={19} /></div><span className="status-pill">{joined ? asString(membership?.role) || "JOINED" : asString(community.membership_type) || asString(community.membership_policy).replaceAll("_", " ")}</span><h2>{asString(community.name)}</h2><p>{asString(community.description)}</p><div className="community-meta"><span><MapPin size={13} />{asString(community.location) || "Online"}</span></div><div className="card-actions"><button className="primary-button" onClick={() => navigate(`/app/communities/${id}`)}>Open Community</button><button className="secondary-button" disabled={busy === id} onClick={() => void changeMembership(id, joined)}>{busy === id ? "Updating…" : joined ? "Leave" : "Join"}</button></div></article>; })}</div></div>;
}

export function CommunityDetailPage({ communityId, refresh, navigate }: {
  communityId: string;
  refresh: () => Promise<void>;
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [detail, setDetail] = useState<CommunityDetail | null>(null);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("Overview");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setDetail(await request<CommunityDetail>(`/api/app/communities/${communityId}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load Community."); }
  }, [communityId, request]);
  useEffect(() => { void load(); }, [load]);

  async function membershipAction() {
    if (!detail) return;
    setBusy(true); setError("");
    try {
      await request(`/api/app/communities/${communityId}/${detail.viewer.joined ? "leave" : "join"}`, { method: "POST", body: detail.viewer.joined ? undefined : "{}" });
      await Promise.all([load(), refresh()]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update membership."); }
    finally { setBusy(false); }
  }
  async function askAgent(event: FormEvent) {
    event.preventDefault(); if (!question.trim()) return;
    setBusy(true); setError("");
    try {
      const response = await request<{ answer: string }>(`/api/app/communities/${communityId}/agent/query`, { method: "POST", body: JSON.stringify({ question }) });
      setAnswer(response.answer);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Community Agent could not answer."); }
    finally { setBusy(false); }
  }

  if (error && !detail) return <div className="beta-page"><button className="text-button" onClick={() => navigate("/app/communities")}>← Communities</button><div className="form-error">{error}</div></div>;
  if (!detail) return <div className="beta-page"><div className="community-loading">Loading Community…</div></div>;
  const community = detail.community;
  const rules = Array.isArray(community.rules) ? community.rules.map(String) : [];
  const requests = Object.entries(detail.open_requests);

  return <div className="beta-page community-detail"><button className="text-button" onClick={() => navigate("/app/communities")}>← All Communities</button><header className="community-hero"><div><span className="eyebrow">{asString(community.membership_type).replaceAll("_", " ")}</span><h1>{asString(community.name)}</h1><p>{asString(community.purpose) || asString(community.description)}</p><div className="community-meta"><span><MapPin size={13} />{asString(community.location) || "Online"}</span>{community.start_time ? <span><CalendarDays size={13} />{asString(community.start_time).slice(0, 10)} – {asString(community.end_time).slice(0, 10)}</span> : null}</div></div><button className={detail.viewer.joined ? "secondary-button" : "primary-button"} disabled={busy} onClick={() => void membershipAction()}>{busy ? "Updating…" : detail.viewer.joined ? "Leave Community" : "Join Community"}</button></header>{error ? <div className="form-error">{error}</div> : null}<div className="community-stats"><article><strong>{detail.counts.members}</strong><span>Members</span></article><article><strong>{detail.counts.active_posts}</strong><span>Open Posts</span></article><article><strong>{detail.counts.active_plans}</strong><span>Visible plans</span></article></div><nav className="community-tabs" aria-label="Community sections">{tabs.map((tab) => <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>{tab}</button>)}</nav>
    {activeTab === "Overview" ? <div className="community-columns"><section className="community-panel"><h2>Purpose</h2><p>{asString(community.purpose) || asString(community.description)}</p><h2>Moderators</h2><p>{detail.moderators.length ? detail.moderators.join(", ") : "No public moderator profiles yet."}</p><h2>How membership works</h2><p>{asString(community.membership_type).replaceAll("_", " ")} · {detail.viewer.joined ? `You are a ${detail.viewer.role || "MEMBER"}.` : "Join to view scoped requests, members, and plans."}</p></section><CommunityAgentCard question={question} answer={answer} busy={busy} setQuestion={setQuestion} onSubmit={askAgent} /></div> : null}
    {activeTab === "Open Requests" ? !detail.viewer.joined ? <LockedPanel /> : requests.some(([, posts]) => posts.length) ? <div className="community-request-sections">{requests.map(([type, posts]) => posts.length ? <section key={type}><div className="section-heading"><h2>{requestLabels[type] || type.replaceAll("_", " ")}</h2><span className="status-pill">{posts.length} OPEN</span></div><div className="request-grid">{posts.map((post) => <button className="request-card" key={asString(post.intent_id)} onClick={() => navigate(`/app/posts/${asString(post.intent_id)}`)}><span className="status-pill">OPEN</span><h3>{asString(post.public_title)}</h3><p>{asString(post.public_summary)}</p><span>Open Post Detail →</span></button>)}</div></section> : null)}</div> : <div className="empty-state"><Building2 /><h3>No open Requests yet</h3><p>Your Personal Agent can publish the first scoped Post for this Community.</p></div> : null}
    {activeTab === "Members & Agents" ? !detail.viewer.joined ? <LockedPanel /> : <div className="member-directory">{detail.members.map((member) => <article key={`${asString(member.personal_agent_id)}-${asString(member.display_name)}`}><div className="member-avatar"><UsersRound size={18} /></div><div><span className="status-pill">{asString(member.role)}</span><h3>{asString(member.display_name)}</h3><p><Bot size={13} />{asString(member.personal_agent)}</p><small>{Array.isArray(member.public_interests) && member.public_interests.length ? member.public_interests.map(String).join(" · ") : "No public interests listed"}</small><small>{String(member.open_post_count || 0)} open Posts{member.shared_connection ? " · Shared Connection" : ""}</small></div></article>)}</div> : null}
    {activeTab === "Plans & Rooms" ? !detail.viewer.joined ? <LockedPanel /> : detail.plans_and_rooms.length ? <div className="request-grid">{detail.plans_and_rooms.map((room) => <button className="request-card" key={asString(room.room_id)} onClick={() => navigate(`/app/rooms/${asString(room.room_id)}`)}><MessageCircle /><span className="status-pill">{asString(room.state) || asString(room.status) || "ACTIVE"}</span><h3>{asString(room.title) || "Community coordination room"}</h3><p>{asString(room.last_material_update)}</p><span>Open visible Room →</span></button>)}</div> : <div className="empty-state"><MessageCircle /><h3>No Community-visible plans yet</h3><p>Private and Agents-only Rooms are intentionally excluded.</p></div> : null}
    {activeTab === "Rules" ? <div className="community-columns"><section className="community-panel rules-panel"><ShieldCheck /><h2>Rules enforced across Posts and Agent contact</h2><ol>{rules.map((rule) => <li key={rule}>{rule}</li>)}</ol><p>Community Agents can apply these rules and route reports, but cannot approve Matches, impersonate moderators, or access protected Memory.</p></section>{detail.viewer.can_moderate ? <CommunityModerationPanel communityId={communityId} /> : null}</div> : null}
  </div>;
}

function CommunityAgentCard({ question, answer, busy, setQuestion, onSubmit }: { question: string; answer: string; busy: boolean; setQuestion: (value: string) => void; onSubmit: (event: FormEvent) => void }) {
  return <section className="community-agent-card"><div><Bot size={19} /><span><strong>Community Agent</strong><small>Public + member-safe scope</small></span></div><p>Ask about rules, Community purpose, or relevant public Posts. It cannot access private Memory or negotiation transcripts.</p><form onSubmit={onSubmit}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What requests need collaborators?" maxLength={500} /><button className="primary-button" disabled={busy || !question.trim()}>Ask</button></form>{answer ? <div className="community-agent-answer">{answer}</div> : null}</section>;
}

function LockedPanel() {
  return <div className="empty-state locked-community"><ShieldCheck /><h3>Members-only Community view</h3><p>Join this Community to see its scoped requests, public member identities, and Community-visible Rooms.</p></div>;
}

function CommunityModerationPanel({ communityId }: { communityId: string }) {
  const { request } = useAuth();
  const [reports, setReports] = useState<RecordValue[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const payload = await request<{ reports: RecordValue[] }>(`/api/app/communities/${communityId}/moderation/reports`);
    setReports(payload.reports);
  }, [communityId, request]);
  useEffect(() => { void load().catch((reason: Error) => setError(reason.message)); }, [load]);
  async function moderate(reportId: string, action: "ACKNOWLEDGE" | "RESOLVE" | "REMOVE_POST") {
    setBusy(`${reportId}:${action}`); setError("");
    try {
      await request(`/api/app/communities/${communityId}/moderation/reports/${reportId}/actions`, { method: "POST", body: JSON.stringify({ action, reason: `Community moderator selected ${action.toLowerCase().replaceAll("_", " ")}` }) });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Moderation action failed."); }
    finally { setBusy(""); }
  }
  return <section className="community-panel community-moderation"><Flag /><h2>Moderator queue</h2><p>Only Community-scoped reports appear here. Private Agent conversations and protected Memory are never available.</p>{error ? <div className="form-error" role="alert">{error}</div> : null}{reports.length ? reports.map((report) => { const id = asString(report.report_id); const canRemove = report.target_type === "POST"; return <article key={id}><span className="status-pill">{asString(report.status)}</span><strong>{asString(report.category)}</strong><p>{asString(report.details)}</p><small>{asString(report.review_notice)}</small><div className="card-actions"><button disabled={Boolean(busy)} onClick={() => void moderate(id, "ACKNOWLEDGE")}>Acknowledge</button><button disabled={Boolean(busy)} onClick={() => void moderate(id, "RESOLVE")}>Resolve</button>{canRemove ? <button className="danger-subtle" disabled={Boolean(busy)} onClick={() => void moderate(id, "REMOVE_POST")}>Remove Post</button> : null}</div></article>; }) : <p>No Community reports need review.</p>}</section>;
}
