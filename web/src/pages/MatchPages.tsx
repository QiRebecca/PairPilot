import {
  CalendarPlus,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Download,
  MapPin,
  MessageSquareMore,
  RefreshCw,
  ShieldCheck,
  UserRoundCheck,
  UsersRound,
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

interface MatchListPayload {
  matches: RecordValue[];
  sections: Record<string, RecordValue[]>;
  count: number;
}

interface MatchDetailPayload {
  match: RecordValue;
  participants: RecordValue[];
  community: RecordValue | null;
  shared_room: RecordValue | null;
  approved_terms: RecordValue;
  remaining_tasks: unknown[];
  contact_cards: RecordValue[];
  calendar_available: boolean;
  cancellation: RecordValue;
  backup: RecordValue;
  outcome_feedback_submitted: boolean;
  change_proposals: RecordValue[];
  safety_reminders: string[];
}

const asString = (value: unknown) => (typeof value === "string" ? value : "");
const sectionLabels: Record<string, string> = {
  NEEDS_ACTION: "Needs Action",
  UPCOMING: "Upcoming",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

function displayTime(value: unknown): string {
  const text = asString(value);
  if (!text) return "Not scheduled";
  const date = new Date(text);
  return Number.isNaN(date.getTime())
    ? text
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function titleFor(match: RecordValue): string {
  const terms = (match.terms || {}) as RecordValue;
  return asString(terms.title) || asString(terms.event) || "Matched plan";
}

export function MatchesPage({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const { request } = useAuth();
  const [payload, setPayload] = useState<MatchListPayload | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void request<MatchListPayload>("/api/app/matches")
      .then(setPayload)
      .catch((reason: Error) => setError(reason.message));
  }, [request]);
  return (
    <div className="beta-page">
      <header className="page-title">
        <span className="eyebrow">EXECUTABLE PLANS</span>
        <h1>Matches</h1>
        <p>
          A Match is the plan both people approved. Open it to coordinate,
          exchange selected contact fields, update the plan, or record the
          outcome.
        </p>
      </header>
      {error ? <div className="form-error">{error}</div> : null}
      {!payload ? (
        <div className="community-loading">Loading Matches…</div>
      ) : payload.count === 0 ? (
        <div className="empty-state">
          <CheckCircle2 />
          <h3>No confirmed Match yet</h3>
          <p>
            Your Agent will bring a negotiated proposal here only after both
            people approve the same version.
          </p>
        </div>
      ) : (
        <div className="match-section-list">
          {Object.entries(sectionLabels).map(([section, label]) => {
            const matches = payload.sections[section] || [];
            return matches.length ? (
              <section key={section}>
                <div className="section-heading">
                  <h2>{label}</h2>
                  <span className="status-pill">{matches.length}</span>
                </div>
                <div className="request-grid">
                  {matches.map((match) => (
                    <button
                      className="request-card match-list-card"
                      key={asString(match.match_id)}
                      onClick={() =>
                        navigate(`/app/matches/${asString(match.match_id)}`)
                      }
                    >
                      <span className="status-pill">
                        {asString(match.state).replaceAll("_", " ")}
                      </span>
                      <h3>{titleFor(match)}</h3>
                      <p>
                        <Clock3 size={12} /> {displayTime(match.start_at)}
                      </p>
                      <p>
                        <MapPin size={12} />{" "}
                        {asString(
                          ((match.terms || {}) as RecordValue).location,
                        ) || "Location to be confirmed"}
                      </p>
                      <span>Open Match Detail →</span>
                    </button>
                  ))}
                </div>
              </section>
            ) : null;
          })}
        </div>
      )}
    </div>
  );
}

export function MatchDetailPage({
  matchId,
  navigate,
}: {
  matchId: string;
  navigate: (path: string) => void;
}) {
  const { request, streamRequest } = useAuth();
  const [payload, setPayload] = useState<MatchDetailPayload | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [publicEmail, setPublicEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [signal, setSignal] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [changeStart, setChangeStart] = useState("");
  const [changeLocation, setChangeLocation] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [cancelConfirmed, setCancelConfirmed] = useState(false);

  const load = useCallback(async () => {
    try {
      setPayload(
        await request<MatchDetailPayload>(`/api/app/matches/${matchId}`),
      );
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load Match.",
      );
    }
  }, [matchId, request]);
  useEffect(() => {
    void load();
  }, [load]);
  const state = asString(payload?.match.state);
  const terms = payload?.approved_terms || {};
  const ownCard = useMemo(
    () => payload?.contact_cards.find((card) => card.is_viewer) || null,
    [payload],
  );

  async function act(
    name: string,
    action: () => Promise<void>,
    success: string,
  ) {
    setBusy(name);
    setError("");
    setNotice("");
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
  async function downloadCalendar() {
    await act(
      "calendar",
      async () => {
        const response = await streamRequest(
          `/api/app/matches/${matchId}/calendar.ics`,
          { headers: { Accept: "text/calendar" } },
        );
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = `pairpilot-${matchId}.ics`;
        link.click();
        URL.revokeObjectURL(url);
      },
      "Calendar file downloaded.",
    );
  }
  async function offerContact(event: FormEvent) {
    event.preventDefault();
    await act(
      "contact",
      () =>
        request(`/api/app/matches/${matchId}/contacts/mine`, {
          method: "PUT",
          body: JSON.stringify({
            public_email: publicEmail || null,
            phone: phone || null,
            whatsapp: null,
            telegram: null,
            signal: signal || null,
            wechat: null,
            linkedin: linkedin || null,
            other_handle: null,
          }),
        }),
      "Only the contact fields you selected were offered to this Match.",
    );
  }
  async function proposeChange(event: FormEvent) {
    event.preventDefault();
    const nextTerms: RecordValue = {};
    if (changeStart) nextTerms.start_at = new Date(changeStart).toISOString();
    if (changeLocation.trim()) nextTerms.location = changeLocation.trim();
    await act(
      "change",
      () =>
        request(`/api/app/matches/${matchId}/changes`, {
          method: "POST",
          body: JSON.stringify({ summary: changeSummary, terms: nextTerms }),
        }),
      "A new plan version was proposed. The current approved plan remains unchanged until both people approve.",
    );
    setChangeSummary("");
    setChangeStart("");
    setChangeLocation("");
  }
  async function cancel(event: FormEvent) {
    event.preventDefault();
    if (!cancelConfirmed) return;
    await act(
      "cancel",
      () =>
        request(`/api/app/matches/${matchId}/cancel`, {
          method: "POST",
          body: JSON.stringify({
            reason: cancelReason,
            reopen_candidate_pool: true,
          }),
        }),
      "Match cancelled, both people notified, and backup search requested.",
    );
  }
  async function submitOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await act(
      "outcome",
      () =>
        request(`/api/app/matches/${matchId}/outcome`, {
          method: "POST",
          body: JSON.stringify({
            did_plan_happen: form.get("happened") === "yes",
            would_coordinate_again: form.get("again") === "yes",
            agreed_term_inaccurate: form.get("inaccurate") === "yes",
            either_person_cancelled: form.get("cancelled") === "yes",
            safety_concern: form.get("safety") === "yes",
            optional_feedback: asString(form.get("feedback")) || null,
          }),
        }),
      "Private outcome saved. It is not shown to the other person.",
    );
  }

  if (!payload)
    return (
      <div className="beta-page">
        {error ? (
          <div className="form-error">{error}</div>
        ) : (
          <div className="community-loading">Loading Match Detail…</div>
        )}
      </div>
    );
  const match = payload.match;
  return (
    <div className="beta-page match-detail">
      <button className="text-button" onClick={() => navigate("/app/matches")}>
        ← All Matches
      </button>
      <header className="match-detail-hero">
        <div>
          <span className="eyebrow">
            MATCH DETAIL · {state.replaceAll("_", " ")}
          </span>
          <h1>{titleFor(match)}</h1>
          <p>
            {payload.participants
              .map((person) => asString(person.display_name))
              .join(" · ")}
            {payload.community ? ` · ${asString(payload.community.name)}` : ""}
          </p>
        </div>
        <div className="match-detail-actions">
          {payload.shared_room ? (
            <button
              className="primary-button"
              onClick={() =>
                navigate(`/app/rooms/${asString(payload.shared_room?.room_id)}`)
              }
            >
              <MessageSquareMore size={15} />
              Open shared Room
            </button>
          ) : null}
          {payload.calendar_available ? (
            <button
              className="secondary-button"
              disabled={!!busy}
              onClick={() => void downloadCalendar()}
            >
              <Download size={15} />
              Add to calendar
            </button>
          ) : null}
        </div>
      </header>
      {notice ? <div className="form-notice">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      <div className="match-plan-facts">
        <article>
          <CalendarPlus />
          <small>Date & time</small>
          <strong>{displayTime(match.start_at)}</strong>
        </article>
        <article>
          <MapPin />
          <small>Location</small>
          <strong>{asString(terms.location) || "Not specified"}</strong>
        </article>
        <article>
          <UsersRound />
          <small>Participants</small>
          <strong>{payload.participants.length}</strong>
        </article>
        <article>
          <ShieldCheck />
          <small>Approval version</small>
          <strong>v{String(match.proposal_version || 1)}</strong>
        </article>
      </div>
      <div className="match-detail-grid">
        <main>
          <section className="match-panel">
            <h2>Approved plan</h2>
            <dl className="match-terms">
              {Object.entries(terms).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
            </dl>
            {payload.remaining_tasks.length ? (
              <>
                <h3>Remaining tasks</h3>
                <ul>
                  {payload.remaining_tasks.map((task, index) => (
                    <li key={index}>{String(task)}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="subtle-copy">
                No remaining operational task is recorded.
              </p>
            )}
          </section>
          <section className="match-panel">
            <h2>Match-scoped Contact Cards</h2>
            <p>
              Login email is never shared. Each person exposes only the fields
              they choose.
            </p>
            {payload.contact_cards.length ? (
              <div className="contact-card-list">
                {payload.contact_cards.map((card) => (
                  <article key={asString(card.contact_card_id)}>
                    <strong>
                      {asString(card.display_name)}
                      {card.is_viewer ? " (you)" : ""}
                    </strong>
                    {Object.entries((card.fields || {}) as RecordValue).map(
                      ([key, value]) => (
                        <span key={key}>
                          {key.replaceAll("_", " ")}: {String(value)}
                        </span>
                      ),
                    )}
                    {!card.is_viewer && !card.accepted_by_viewer ? (
                      <button
                        className="secondary-button"
                        disabled={!!busy}
                        onClick={() =>
                          void act(
                            "accept",
                            () =>
                              request(
                                `/api/app/matches/${matchId}/contacts/${asString(card.contact_card_id)}/accept`,
                                { method: "POST", body: "{}" },
                              ),
                            "Contact Card accepted for this Match.",
                          )
                        }
                      >
                        <UserRoundCheck size={14} />
                        Accept card
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle-copy">
                No contact fields have been offered.
              </p>
            )}
            <form className="contact-form" onSubmit={offerContact}>
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
                aria-label="Signal"
                placeholder="Signal (optional)"
                value={signal}
                onChange={(event) => setSignal(event.target.value)}
              />
              <input
                aria-label="LinkedIn"
                placeholder="LinkedIn (optional)"
                value={linkedin}
                onChange={(event) => setLinkedin(event.target.value)}
              />
              <button className="primary-button" disabled={!!busy}>
                Offer selected fields
              </button>
              {ownCard ? (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={!!busy}
                  onClick={() =>
                    void act(
                      "revoke",
                      () =>
                        request(`/api/app/matches/${matchId}/contacts/mine`, {
                          method: "DELETE",
                        }),
                      "Your Contact Card was revoked.",
                    )
                  }
                >
                  Revoke mine
                </button>
              ) : null}
            </form>
          </section>
          {state !== "CANCELLED" && state !== "COMPLETED" ? (
            <section className="match-panel">
              <h2>Propose a material change</h2>
              <p>
                A proposed time or place becomes a new version; the current plan
                remains authoritative until both people approve.
              </p>
              <form className="match-action-form" onSubmit={proposeChange}>
                <label>
                  What is changing?
                  <textarea
                    required
                    maxLength={500}
                    value={changeSummary}
                    onChange={(event) => setChangeSummary(event.target.value)}
                  />
                </label>
                <label>
                  New start (optional)
                  <input
                    type="datetime-local"
                    value={changeStart}
                    onChange={(event) => setChangeStart(event.target.value)}
                  />
                </label>
                <label>
                  New location (optional)
                  <input
                    maxLength={120}
                    value={changeLocation}
                    onChange={(event) => setChangeLocation(event.target.value)}
                  />
                </label>
                <button
                  className="secondary-button"
                  disabled={!!busy || (!changeStart && !changeLocation.trim())}
                >
                  <RefreshCw size={14} />
                  Create approval version
                </button>
              </form>
              {payload.change_proposals.map((change) => (
                <div
                  className="change-proposal"
                  key={asString(change.change_id)}
                >
                  <span className="status-pill">{asString(change.status)}</span>
                  <strong>Version {String(change.version)}</strong>
                  <p>{asString(change.summary)}</p>
                  {asString(change.status) === "AWAITING_APPROVALS" &&
                  asString(change.viewer_decision_status) === "OPEN" ? (
                    <button
                      className="primary-button"
                      disabled={!!busy}
                      onClick={() =>
                        void act(
                          "approve-change",
                          () =>
                            request(
                              `/api/app/matches/${matchId}/changes/${asString(change.change_id)}/approve`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  version: Number(change.version),
                                  confirmation: `APPROVE CHANGE VERSION ${Number(change.version)}`,
                                }),
                              },
                            ),
                          "Your approval was recorded. The current plan changes only after the other person approves the same version.",
                        )
                      }
                    >
                      Approve version {String(change.version)}
                    </button>
                  ) : null}
                </div>
              ))}
            </section>
          ) : null}
          <section className="match-panel">
            <h2>Private outcome</h2>
            {payload.outcome_feedback_submitted ? (
              <div className="form-notice">
                Your outcome was recorded privately.
              </div>
            ) : (
              <form className="outcome-form" onSubmit={submitOutcome}>
                <label>
                  Did the plan happen?
                  <select name="happened">
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
                <label>
                  Coordinate again?
                  <select name="again">
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
                <label>
                  Agreed term inaccurate?
                  <select name="inaccurate">
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </label>
                <label>
                  Did either person cancel?
                  <select name="cancelled">
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </label>
                <label>
                  Safety concern?
                  <select name="safety">
                    <option value="no">No</option>
                    <option value="yes">Yes — send to moderation</option>
                  </select>
                </label>
                <label>
                  Optional private feedback
                  <textarea name="feedback" maxLength={1000} />
                </label>
                <button className="primary-button" disabled={!!busy}>
                  Save private outcome
                </button>
              </form>
            )}
          </section>
        </main>
        <aside>
          <section className="match-panel safety-panel">
            <CircleAlert />
            <h2>Safety</h2>
            {payload.safety_reminders.map((reminder) => (
              <p key={reminder}>{reminder}</p>
            ))}
          </section>
          {state === "CANCELLED" ? (
            <section className="match-panel">
              <XCircle />
              <h2>Cancelled</h2>
              <p>
                {asString(payload.cancellation.reason) || "No reason recorded."}
              </p>
              {payload.backup.available ? (
                <button
                  className="primary-button full"
                  disabled={!!busy}
                  onClick={() =>
                    void act(
                      "backup",
                      () =>
                        request(`/api/app/matches/${matchId}/backup/activate`, {
                          method: "POST",
                          body: "{}",
                        }),
                      "The highest-ranked available backup moved into active coordination.",
                    )
                  }
                >
                  Activate best backup
                </button>
              ) : null}
            </section>
          ) : state !== "COMPLETED" ? (
            <>
              <section className="match-panel">
                <CheckCircle2 />
                <h2>Plan completed?</h2>
                <p>
                  Completion enables an authoritative private outcome check-in.
                </p>
                <button
                  className="secondary-button full"
                  disabled={!!busy}
                  onClick={() =>
                    void act(
                      "complete",
                      () =>
                        request(`/api/app/matches/${matchId}/complete`, {
                          method: "POST",
                          body: JSON.stringify({
                            confirmation: "MARK PLAN COMPLETED",
                          }),
                        }),
                      "Match marked completed.",
                    )
                  }
                >
                  Mark completed
                </button>
              </section>
              <section className="match-panel danger-panel">
                <XCircle />
                <h2>Cancel Match</h2>
                <form className="match-action-form" onSubmit={cancel}>
                  <label>
                    Reason
                    <textarea
                      required
                      maxLength={500}
                      value={cancelReason}
                      onChange={(event) => setCancelReason(event.target.value)}
                    />
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={cancelConfirmed}
                      onChange={(event) =>
                        setCancelConfirmed(event.target.checked)
                      }
                    />{" "}
                    Notify both people, release commitments, and restart backup
                    search.
                  </label>
                  <button
                    className="danger-button"
                    disabled={!!busy || !cancelConfirmed}
                  >
                    Cancel Match
                  </button>
                </form>
              </section>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
