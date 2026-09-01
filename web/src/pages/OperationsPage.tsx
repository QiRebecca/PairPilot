import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Blocks,
  Bot,
  Building2,
  FileWarning,
  Gauge,
  History,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UsersRound,
} from "lucide-react";
import { useAuth } from "../auth";

type RecordValue = Record<string, unknown>;
type Section =
  | "System Health"
  | "Users"
  | "Communities"
  | "Posts"
  | "Reports"
  | "Moderation"
  | "Agent Runs"
  | "Failed Jobs"
  | "Pub/Sub and DLQ"
  | "Model Usage"
  | "Quotas"
  | "Account Deletion"
  | "Analytics"
  | "Audit";

const sections: Array<[Section, typeof Activity]> = [
  ["System Health", Activity],
  ["Users", UsersRound],
  ["Communities", Building2],
  ["Posts", Blocks],
  ["Reports", FileWarning],
  ["Moderation", ShieldCheck],
  ["Agent Runs", Bot],
  ["Failed Jobs", RefreshCw],
  ["Pub/Sub and DLQ", Gauge],
  ["Model Usage", BarChart3],
  ["Quotas", Gauge],
  ["Account Deletion", Trash2],
  ["Analytics", BarChart3],
  ["Audit", History],
];

const asString = (value: unknown) =>
  typeof value === "string" ? value : value == null ? "—" : String(value);
const records = (value: unknown): RecordValue[] =>
  Array.isArray(value) ? (value as RecordValue[]) : [];
const record = (value: unknown): RecordValue =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as RecordValue)
    : {};
const label = (value: string) => value.replaceAll("_", " ");

function MetricGrid({ values }: { values: RecordValue }) {
  return (
    <div className="operations-metrics">
      {Object.entries(values).map(([key, value]) => (
        <article key={key}>
          <small>{label(key)}</small>
          <strong>{asString(value)}</strong>
        </article>
      ))}
    </div>
  );
}

function DataTable({ rows, empty }: { rows: RecordValue[]; empty: string }) {
  if (!rows.length) return <p className="operations-empty">{empty}</p>;
  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row))),
  ).filter((key) => !["details", "reason"].includes(key));
  return (
    <div className="operations-table-wrap">
      <table className="operations-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{label(column)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={asString(row.audit_id || row.run_id || row.uid || index)}>
              {columns.map((column) => (
                <td key={column}>{asString(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OperationsPage() {
  const { request } = useAuth();
  const [section, setSection] = useState<Section>("System Health");
  const [dashboard, setDashboard] = useState<RecordValue | null>(null);
  const [reportDetail, setReportDetail] = useState<RecordValue | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    const payload = await request<RecordValue>("/api/admin/dashboard");
    setDashboard(payload);
  }, [request]);

  useEffect(() => {
    void refresh().catch((reason: Error) => setError(reason.message));
  }, [refresh]);

  const act = useCallback(
    async (key: string, path: string, body: RecordValue) => {
      setBusy(key);
      setError("");
      setNotice("");
      try {
        await request(path, {
          method: "POST",
          body: JSON.stringify(body),
        });
        setNotice("The operation was accepted and recorded in Audit.");
        await refresh();
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : "Operation failed.",
        );
      } finally {
        setBusy("");
      }
    },
    [refresh, request],
  );

  const counts = useMemo(() => record(dashboard?.counts), [dashboard]);
  if (error && !dashboard) {
    return (
      <main className="operations-page">
        <header>
          <p>EXPLICIT SERVER ROLE REQUIRED</p>
          <h1>Operations console</h1>
        </header>
        <div className="form-error" role="alert">
          {error}
        </div>
      </main>
    );
  }
  if (!dashboard) {
    return (
      <div className="beta-loading" role="status">
        <LoaderCircle className="spin" /> Loading privacy-safe operations…
      </div>
    );
  }

  const reports = records(dashboard.reports);
  const failedJobs = records(dashboard.failed_jobs);
  const deadLetters = records(dashboard.dead_letters);
  const quotas = records(dashboard.quotas);

  return (
    <main className="operations-page">
      <header className="operations-heading">
        <div>
          <p>SERVER-AUTHORIZED · PRIVACY-BOUNDED</p>
          <h1>Operations console</h1>
          <span>{asString(dashboard.privacy_notice)}</span>
        </div>
        <button
          onClick={() => void refresh()}
          aria-label="Refresh operations data"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </header>
      <MetricGrid values={counts} />
      {error ? (
        <div className="form-error" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="operations-notice" role="status">
          {notice}
        </div>
      ) : null}
      <div className="operations-layout">
        <nav className="operations-nav" aria-label="Admin sections">
          {sections.map(([name, Icon]) => (
            <button
              key={name}
              className={name === section ? "active" : ""}
              aria-current={name === section ? "page" : undefined}
              onClick={() => setSection(name)}
            >
              <Icon size={15} /> {name}
            </button>
          ))}
        </nav>
        <section className="operations-panel">
          <h2>{section}</h2>
          {section === "System Health" ? (
            <MetricGrid values={record(dashboard.system_health)} />
          ) : null}
          {section === "Users" ? (
            <DataTable
              rows={records(dashboard.users)}
              empty="No users recorded."
            />
          ) : null}
          {section === "Communities" ? (
            <DataTable
              rows={records(dashboard.communities)}
              empty="No Communities recorded."
            />
          ) : null}
          {section === "Posts" ? (
            <DataTable
              rows={records(dashboard.posts)}
              empty="No Posts recorded."
            />
          ) : null}
          {section === "Reports" ? (
            <div className="operations-stack">
              {reports.length ? (
                reports.map((report) => {
                  const id = asString(report.report_id);
                  return (
                    <article className="operations-action-card" key={id}>
                      <div>
                        <strong>{asString(report.category)} report</strong>
                        <span>
                          {asString(report.target_type)} ·{" "}
                          {asString(report.target_id)}
                        </span>
                        <small>Status: {asString(report.status)}</small>
                      </div>
                      <div className="operations-actions">
                        <button
                          onClick={() => {
                            setBusy(`inspect:${id}`);
                            void request<RecordValue>(
                              `/api/admin/reports/${id}`,
                            )
                              .then(setReportDetail)
                              .catch((reason: Error) =>
                                setError(reason.message),
                              )
                              .finally(() => setBusy(""));
                          }}
                        >
                          {busy === `inspect:${id}` ? "Loading…" : "Inspect"}
                        </button>
                        <button
                          onClick={() =>
                            void act(
                              `ack:${id}`,
                              `/api/admin/reports/${id}/actions`,
                              {
                                action: "ACKNOWLEDGE",
                                reason: "Accepted into operator review",
                              },
                            )
                          }
                        >
                          Acknowledge
                        </button>
                        <button
                          className="danger-subtle"
                          onClick={() =>
                            void act(
                              `dismiss:${id}`,
                              `/api/admin/reports/${id}/actions`,
                              {
                                action: "DISMISS",
                                reason:
                                  "Operator found no actionable policy violation",
                              },
                            )
                          }
                        >
                          Dismiss
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <p className="operations-empty">
                  No reports in the bounded window.
                </p>
              )}
              {reportDetail ? (
                <aside className="report-inspector" aria-live="polite">
                  <strong>Report {asString(reportDetail.report_id)}</strong>
                  <p>{asString(reportDetail.details)}</p>
                  <small>{asString(reportDetail.review_notice)}</small>
                  <button onClick={() => setReportDetail(null)}>
                    Close inspector
                  </button>
                </aside>
              ) : null}
            </div>
          ) : null}
          {section === "Moderation" ? (
            <DataTable
              rows={records(dashboard.moderation)}
              empty="No moderation actions recorded."
            />
          ) : null}
          {section === "Agent Runs" ? (
            <DataTable
              rows={records(dashboard.agent_runs)}
              empty="No Agent runs recorded."
            />
          ) : null}
          {section === "Failed Jobs" ? (
            <JobActions
              rows={failedJobs}
              busy={busy}
              onAction={(id, action) =>
                act(`${action}:${id}`, `/api/admin/failed-jobs/${id}/actions`, {
                  action,
                  idempotency_key: `${action.toLowerCase()}-${id}-${Date.now()}`,
                  reason:
                    "Explicit operator action from the operations console",
                })
              }
            />
          ) : null}
          {section === "Pub/Sub and DLQ" ? (
            <JobActions
              rows={deadLetters.map((row) => ({
                ...row,
                job_id: row.message_id,
              }))}
              busy={busy}
              dlq
              onAction={(id) =>
                act(
                  `MOVE_FROM_DLQ:${id}`,
                  `/api/admin/failed-jobs/${id}/actions`,
                  {
                    action: "MOVE_FROM_DLQ",
                    idempotency_key: `move-${id}-${Date.now()}`,
                    reason: "Explicit operator DLQ requeue",
                  },
                )
              }
            />
          ) : null}
          {section === "Model Usage" ? (
            <MetricGrid values={record(dashboard.model_usage)} />
          ) : null}
          {section === "Quotas" ? (
            <QuotaEditor rows={quotas} request={request} refresh={refresh} />
          ) : null}
          {section === "Account Deletion" ? (
            <DataTable
              rows={records(dashboard.account_deletions)}
              empty="No deletion requests recorded."
            />
          ) : null}
          {section === "Analytics" ? (
            <Analytics values={record(dashboard.analytics)} />
          ) : null}
          {section === "Audit" ? (
            <DataTable
              rows={records(dashboard.audit)}
              empty="No operator audit records."
            />
          ) : null}
        </section>
      </div>
    </main>
  );
}

function JobActions({
  rows,
  busy,
  dlq = false,
  onAction,
}: {
  rows: RecordValue[];
  busy: string;
  dlq?: boolean;
  onAction: (id: string, action: "RETRY" | "DISMISS" | "MOVE_FROM_DLQ") => void;
}) {
  if (!rows.length)
    return <p className="operations-empty">No items in this queue.</p>;
  return (
    <div className="operations-stack">
      {rows.map((row) => {
        const id = asString(row.job_id);
        return (
          <article className="operations-action-card" key={id}>
            <div>
              <strong>
                {asString(row.job_type || row.event_type || "Failed job")}
              </strong>
              <span>{id}</span>
              <small>
                {asString(row.status)} · task {asString(row.task_id)}
              </small>
            </div>
            <div className="operations-actions">
              <button
                disabled={Boolean(busy)}
                onClick={() => onAction(id, dlq ? "MOVE_FROM_DLQ" : "RETRY")}
              >
                {dlq ? "Move from DLQ" : "Retry idempotently"}
              </button>
              {!dlq ? (
                <button
                  disabled={Boolean(busy)}
                  onClick={() => onAction(id, "DISMISS")}
                >
                  Dismiss
                </button>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function QuotaEditor({
  rows,
  request,
  refresh,
}: {
  rows: RecordValue[];
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState("");
  if (!rows.length)
    return <p className="operations-empty">No quotas recorded.</p>;
  return (
    <div className="operations-stack">
      {rows.map((quota) => {
        const uid = asString(quota.owner_uid);
        return (
          <form
            className="quota-card"
            key={uid}
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              setBusy(uid);
              void request(`/api/admin/quotas/${uid}`, {
                method: "PUT",
                body: JSON.stringify({
                  active_task_limit: Number(form.get("active_task_limit")),
                  concurrent_negotiations_per_task: Number(
                    form.get("concurrent_negotiations_per_task"),
                  ),
                  new_contacts_per_task: Number(
                    form.get("new_contacts_per_task"),
                  ),
                  daily_agent_turn_limit: Number(
                    form.get("daily_agent_turn_limit"),
                  ),
                  reason: "Explicit operator quota adjustment",
                }),
              })
                .then(refresh)
                .finally(() => setBusy(""));
            }}
          >
            <strong>{uid}</strong>
            {[
              "active_task_limit",
              "concurrent_negotiations_per_task",
              "new_contacts_per_task",
              "daily_agent_turn_limit",
            ].map((field) => (
              <label key={field}>
                {label(field)}
                <input
                  name={field}
                  type="number"
                  min="1"
                  max={field === "daily_agent_turn_limit" ? "1000" : "100"}
                  defaultValue={asString(quota[field])}
                  required
                />
              </label>
            ))}
            <button disabled={busy === uid} type="submit">
              {busy === uid ? "Saving…" : "Save audited quota"}
            </button>
          </form>
        );
      })}
    </div>
  );
}

function Analytics({ values }: { values: RecordValue }) {
  const lifecycle = record(values.lifecycle_counts);
  const rates = Object.fromEntries(
    Object.entries(values).filter(([key]) => key !== "lifecycle_counts"),
  );
  return (
    <div className="operations-stack">
      <h3>Lifecycle event counts</h3>
      <MetricGrid values={lifecycle} />
      <h3>Derived product metrics</h3>
      <MetricGrid values={rates} />
      <p className="operations-empty">
        Analytics contains counts and timestamps only—never Post, Room, or
        Memory text.
      </p>
    </div>
  );
}
