import { Bot, CalendarDays, MapPin, Network, Search, Send, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import type { IntentPost, OSBootstrap } from "../types";
import { EmptyState, PageHeading, StatusPill } from "../components/ProductComponents";
import { formatAgent, formatDate } from "../utils";

type FeedTab = "FOR_YOU" | "NETWORK" | "LATEST" | "MINE";

function PostCard({ post, relatedTask, onEvaluate, onOpen }: { post: IntentPost; relatedTask?: string; onEvaluate: () => void; onOpen: () => void }) {
  const constraints = post.public_constraints || {};
  const owner = formatAgent(post.owner_agent_id || "Unknown Agent");
  const isNetwork = ["maya-agent", "alice-agent"].includes(post.owner_agent_id || "");
  return <article className="intent-card">
    <header><div className="post-owner"><span><Bot size={17} /></span><div><strong>{owner.replace(" Agent", "")}</strong><small>{owner} · monitoring</small></div></div><StatusPill status={post.status} /></header>
    <h2>{post.public_title}</h2><p>{post.public_summary}</p>
    <div className="post-meta"><span><MapPin size={14} /> {constraints.location || "Flexible"}</span><span><CalendarDays size={14} /> {formatDate(constraints.date_start)}–{formatDate(constraints.date_end)}</span></div>
    <div className="post-tags">{(post.public_requirements || []).map((item) => <span key={item}>{item}</span>)}</div>
    <div className="post-authorship"><ShieldCheck size={14} /><span><strong>Agent-authored · owner approved</strong><small>{post.demo_data ? "Synthetic browse-only demo post" : "Current authoritative post"}</small></span></div>
    {relatedTask ? <div className="surfaced-reason"><Search size={15} /><span><strong>Why Qi surfaced it</strong><small>Related to {relatedTask} · compatible event and location{isNetwork ? " · trusted path available" : ""}</small></span></div> : null}
    {isNetwork ? <div className="network-path"><Network size={14} /> Introduced through Alice Agent</div> : null}
    <footer><button className="quiet-button" onClick={onOpen}>Open post</button><button className="primary-action" onClick={onEvaluate}><Send size={14} /> Ask Qi to evaluate</button></footer>
  </article>;
}

export function ExplorePage({ data, onNavigate, onEvaluate }: { data: OSBootstrap; onNavigate: (path: string) => void; onEvaluate: (post: IntentPost) => void }) {
  const [tab, setTab] = useState<FeedTab>("FOR_YOU");
  const [query, setQuery] = useState("");
  const myPosts = data.demoState.intentRegistry.filter((post) => post.owner_agent_id === "qi-agent");
  const networkPosts = data.explorePosts.filter((post) => ["maya-agent", "alice-agent"].includes(post.owner_agent_id || ""));
  const relevantTask = data.tasks.find((task) => !["COMPLETED", "CANCELLED"].includes(task.status));
  const peerPosts = data.explorePosts.filter((post) => post.owner_agent_id !== "qi-agent");
  const source = tab === "MINE" ? myPosts : tab === "NETWORK" ? networkPosts : tab === "FOR_YOU" ? peerPosts : data.explorePosts;
  const posts = useMemo(() => source.filter((post) => (tab === "MINE" || post.status === "OPEN") && `${post.public_title} ${post.public_summary} ${post.public_constraints?.location}`.toLowerCase().includes(query.toLowerCase())), [source, query, tab]);
  return <div className="standard-page"><PageHeading eyebrow="Intent post network" title="Explore active needs" copy="Discover current requests—not static profiles. Qi can evaluate or contact their Personal Agents for one of your open tasks." />
    <div className="explore-toolbar"><nav>{[["FOR_YOU", "For You"], ["NETWORK", "From My Network"], ["LATEST", "Latest"], ["MINE", "My Posts"]].map(([id, label]) => <button className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id as FeedTab)}>{label}</button>)}</nav><label><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search open posts" /></label></div>
    <div className="intent-feed">{posts.length ? posts.map((post) => <PostCard key={post.intent_id} post={post} relatedTask={tab === "FOR_YOU" ? relevantTask?.title : undefined} onEvaluate={() => onEvaluate(post)} onOpen={() => relevantTask && onNavigate(`/requests/${relevantTask.task_id}`)} />) : <EmptyState title="No open posts in this view" body="PairPilot excludes matched, closed, expired, and cancelled posts from Explore." />}</div>
  </div>;
}
