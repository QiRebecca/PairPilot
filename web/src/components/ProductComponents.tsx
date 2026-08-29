import {
  ArrowRight,
  Bot,
  Check,
  ExternalLink,
  Fingerprint,
  LockKeyhole,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useState } from "react";
import type {
  ApprovalRequest,
  ConversationMessage,
  Decision,
  DraftReview,
  PresentationDirective,
} from "../types";

export const sampleGoal = `Find me a female roommate for ICML in Seoul from July 6 to July 10.
A quiet overnight environment matters more than getting the lowest price.
I can accept partial date overlap if the additional cost stays below $70.`;

export function StatusPill({ status }: { status?: string }) {
  return <span className={`status-chip status-${(status || "idle").toLowerCase()}`}>{(status || "Idle").replaceAll("_", " ")}</span>;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="empty-state"><Sparkles size={20} /><strong>{title}</strong><p>{body}</p></div>;
}

export function PageHeading({ eyebrow, title, copy, action }: { eyebrow: string; title: string; copy?: string; action?: React.ReactNode }) {
  return <header className="page-heading"><div><span>{eyebrow}</span><h1>{title}</h1>{copy ? <p>{copy}</p> : null}</div>{action}</header>;
}

export function Conversation({
  title,
  subtitle,
  messages,
  directives,
  busy,
  placeholder,
  sample,
  onSend,
  onDirective,
}: {
  title: string;
  subtitle: string;
  messages: ConversationMessage[];
  directives: PresentationDirective[];
  busy: boolean;
  placeholder: string;
  sample?: string;
  onSend: (content: string) => void;
  onDirective: (directive: PresentationDirective) => void;
}) {
  const [draft, setDraft] = useState("");
  const directiveMap = new Map(directives.map((item) => [item.directive_id, item]));
  const send = () => {
    if (draft.trim().length < 2 || busy) return;
    onSend(draft.trim());
    setDraft("");
  };
  return <section className="conversation-panel">
    <header className="conversation-header"><span className="agent-avatar large"><Bot size={21} /></span><div><h2>{title}</h2><p>{subtitle}</p></div><span className="online-label"><i /> Online</span></header>
    <div className="message-list">
      {messages.length === 0 ? <div className="conversation-welcome"><span className="agent-orbit"><Bot size={27} /></span><h1>What can I take care of?</h1><p>Tell me the outcome you want. I’ll create an isolated request, find matching active posts, coordinate with their agents, and return when your judgment is needed.</p><button onClick={() => setDraft(sample || sampleGoal)}>Try the ICML roommate example <ArrowRight size={14} /></button></div> : messages.map((message) => {
        const fromUser = message.role === "USER";
        const messageDirectives = (message.presentation_directive_ids || []).map((id) => directiveMap.get(id)).filter(Boolean) as PresentationDirective[];
        return <article className={`chat-message ${fromUser ? "from-user" : "from-agent"}`} key={message.message_id}>
          <span className="chat-avatar">{fromUser ? <UserRound size={15} /> : <Bot size={15} />}</span>
          <div><small>{fromUser ? "You" : "Qi Agent"}</small><p>{message.content}</p>{messageDirectives.map((directive) => <button className="directive-card" key={directive.directive_id} onClick={() => onDirective(directive)}><span><strong>{directive.action.replaceAll("_", " ")}</strong><small>{directive.explanation}</small></span><ExternalLink size={15} /></button>)}</div>
        </article>;
      })}
      {busy ? <article className="chat-message from-agent"><span className="chat-avatar"><Bot size={15} /></span><div><small>Qi Agent</small><p className="thinking"><i /><i /><i /></p></div></article> : null}
    </div>
    <div className="chat-composer"><textarea aria-label={`Message ${title}`} rows={3} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={placeholder} /><div><span><ShieldCheck size={13} /> Private with your Personal Agent</span><button aria-label="Send message" onClick={send} disabled={busy || draft.trim().length < 2}><Send size={17} /></button></div></div>
  </section>;
}

export interface ReviewForm {
  intentId: string; title: string; summary: string; event: string; location: string;
  dateStart: string; dateEnd: string; gender: string; publicRequirements: string;
  quietImportance: string; maximumCost: number; partialOverlap: boolean;
}

function formFromReview(review: DraftReview): ReviewForm {
  const post = review.publicPost;
  const constraints = post.public_constraints || {};
  return { intentId: post.intent_id || "", title: post.public_title || "", summary: post.public_summary || "", event: constraints.event || "ICML", location: constraints.location || "Seoul", dateStart: constraints.date_start || "2026-07-06", dateEnd: constraints.date_end || "2026-07-10", gender: constraints.roommate_gender_preference || "female", publicRequirements: (post.public_requirements || []).join(", "), quietImportance: review.agentOnly.quiet_overnight_compatibility?.importance || "high", maximumCost: review.agentOnly.maximum_additional_cost_usd ?? 70, partialOverlap: review.agentOnly.partial_date_overlap_allowed ?? true };
}

export function DraftReviewCard({ review, busy, onPublish }: { review: DraftReview; busy: boolean; onPublish: (form: ReviewForm) => void }) {
  const [form, setForm] = useState(() => formFromReview(review));
  const set = <K extends keyof ReviewForm>(key: K, value: ReviewForm[K]) => setForm((current) => ({ ...current, [key]: value }));
  return <section className="draft-review">
    <div className="draft-review-head"><div><span><Fingerprint size={14} /> Human review required</span><h2>Review what Qi will publish</h2></div><StatusPill status="DRAFT" /></div>
    <div className="review-columns">
      <article className="review-surface public"><label>Public post</label><input value={form.title} onChange={(e) => set("title", e.target.value)} /><textarea rows={3} value={form.summary} onChange={(e) => set("summary", e.target.value)} /><div className="field-pair"><input value={form.event} onChange={(e) => set("event", e.target.value)} /><input value={form.location} onChange={(e) => set("location", e.target.value)} /></div><div className="field-pair"><input type="date" value={form.dateStart} onChange={(e) => set("dateStart", e.target.value)} /><input type="date" value={form.dateEnd} onChange={(e) => set("dateEnd", e.target.value)} /></div><input value={form.publicRequirements} onChange={(e) => set("publicRequirements", e.target.value)} /></article>
      <div className="review-side"><article className="review-surface agent-only"><label><Bot size={14} /> Agent-only matching notes</label><select value={form.quietImportance} onChange={(e) => set("quietImportance", e.target.value)}><option value="high">Quiet nights · high priority</option><option value="medium">Quiet nights · medium priority</option><option value="low">Quiet nights · low priority</option></select><div className="field-pair"><input type="number" value={form.maximumCost} onChange={(e) => set("maximumCost", Number(e.target.value))} /><label className="check-field"><input type="checkbox" checked={form.partialOverlap} onChange={(e) => set("partialOverlap", e.target.checked)} /> Partial dates OK</label></div></article><article className="review-surface protected"><label><LockKeyhole size={14} /> Protected</label><p>{review.protected.disclosure}</p></article></div>
    </div>
    <footer><span>Qi may negotiate within these boundaries. Booking, payment, and commitment always require you.</span><button onClick={() => onPublish(form)} disabled={busy}><Send size={15} /> {busy ? "Publishing…" : "Approve post & publish"}</button></footer>
  </section>;
}

export function DecisionCard({ decision, approval, busy, onApprove, onReject, onOpen }: { decision: Decision; approval?: ApprovalRequest; busy: boolean; onApprove: () => void; onReject: () => void; onOpen: () => void }) {
  const isApproval = decision.type === "APPROVE_PROPOSAL" && approval;
  return <article className="decision-card"><header><span><Fingerprint size={15} /> Needs your decision</span><StatusPill status={decision.status} /></header><h3>{decision.title}</h3><p>{decision.summary}</p>{isApproval ? <div className="decision-contract"><div><span>Candidate</span><strong>{approval.candidateIdentitySummary}</strong></div><div><span>Shared dates</span><strong>{approval.sharedDates?.start} → {approval.sharedDates?.end}</strong></div><div><span>Additional cost</span><strong>${approval.costDifferenceUsd} / ${approval.delegatedMaximumUsd} max</strong></div><div><span>Proposal</span><strong>Version {approval.proposalVersion}</strong></div></div> : null}<footer>{isApproval ? <><button className="quiet-button" onClick={onReject} disabled={busy}>Reject</button><button className="primary-action" onClick={onApprove} disabled={busy}><Check size={15} /> Approve exact effect</button></> : <button className="primary-action" onClick={onOpen}>Review now <ArrowRight size={14} /></button>}</footer></article>;
}

export function TrustLegend() {
  return <div className="trust-legend"><span><ShieldCheck size={13} /> Verified</span><span><Bot size={13} /> Peer-reported</span><span><Fingerprint size={13} /> Negotiated</span></div>;
}
