# Startup V2 safety and operations architecture

Updated: 2026-09-01

Status: `PARTIAL`

Phase 9 now has a server-authorized operational control plane, not just a
decorative aggregate dashboard. It remains `PARTIAL` because candidate
deployment, real Pub/Sub/DLQ provider metrics and actions, multi-user moderation
acceptance, and failure-injection acceptance have not run.

## Authority boundaries

- `/api/admin/*` requires the Firebase token's explicit `admin: true` claim on
  every request. Hiding the route in the frontend is not the authorization
  boundary.
- Community moderation requires an active `MODERATOR` or `ADMIN` membership in
  the exact Community. A global administrator is also allowed.
- A Community moderator cannot query another Community's reports.
- Operations projections omit authentication email, private Post data,
  conversations, Room message content, Memory content, model prompts, and model
  responses.
- Report narratives are returned only by an explicit authorized report-detail
  request or to the correctly scoped Community moderator. React renders them as
  text, and the UI labels them as untrusted input.

## Operational actions

### Reports and moderation

Supported actions are:

- acknowledge;
- resolve;
- dismiss (global admin only);
- remove a reported Community Post;
- suspend the target Community membership when authoritative target metadata is
  available.

Every action writes both `moderation_actions` and `audit_events`. Removing a Post
closes it to new contacts and records the moderation outcome. Report creation now
records derived `community_id` and `target_owner_uid` when the reported entity
provides them; it does not trust these values from the client.

### Failed jobs and dead letters

The operator may retry a failed job, dismiss it, or move a dead-letter record
back into the retry stream. Each request requires an idempotency key and creates
a deterministic `operator_job_actions` record. A repeated request with the same
key returns the first operation without incrementing the attempt counter again.

Retry events contain only the job ID, source collection, and operation ID. They
do not copy a job's private payload into Pub/Sub.

### Quotas

The console exposes bounded edits for active Requests, concurrent negotiations,
new contacts, and daily Agent turns. Pydantic enforces hard upper and lower
bounds. Each mutation stores the operator and creates an audit event.

## Admin console sections

`/app/admin` now provides:

- System Health;
- Users;
- Communities;
- Posts;
- Reports;
- Moderation;
- Agent Runs;
- Failed Jobs;
- Pub/Sub and DLQ;
- Model Usage;
- Quotas;
- Account Deletion;
- Analytics;
- Audit.

System health does not fabricate cloud-provider observability. Cloud Run uses
`K_REVISION` when present. In-process outbox and stored DLQ counts are shown,
while provider backlog metrics are labelled `NOT_CONFIGURED_IN_PROCESS` until an
authorized Google Cloud monitoring adapter is added.

Model cost is also not fabricated. Tokens, runs, failures, and retries are shown
from authoritative records; cost remains unavailable until an explicit, versioned
pricing table is configured.

## Privacy-safe analytics

The analytics projection uses event names, counts, statuses, and timestamps. It
does not return event payload text. It includes lifecycle counts and derived
proposal, dual-approval, completion, cancellation, Connection reuse, and Memory
confirmation metrics. Some requested startup metrics still need canonical event
timestamps and candidate acceptance data, so the analytics capability remains
partial.

## Recovery and existing privacy operations

The existing authenticated account export and deferred deletion workflow remain
active. Deletion immediately removes the user from new social activity, closes
Posts, cancels open tasks/proposals, revokes Room participation and contact
retrieval, and schedules private erasure while preserving minimum safety/audit
records.

## Local verification

- Ruff: passed for all packages, services, and tests.
- Python unit suite: 157 passed; zero failed; two dependency deprecation
  warnings.
- ESLint: passed.
- TypeScript: passed.
- Frontend tests: 7 passed; zero failed.
- Frontend production build: passed.
- Candidate environment: not deployed.
- Independently authenticated users exercised in this phase: zero.

## Remaining gates

- Bind provider-native Pub/Sub backlog, subscription, and DLQ metrics to the
  console without broadening service-account permissions unnecessarily.
- Prove real retry and DLQ requeue against isolated candidate subscriptions.
- Run administrator and Community-moderator browser acceptance with independent
  Firebase principals.
- Exercise block/report/moderation across Explore, Personal Agents, Rooms, warm
  introductions, and later discovery.
- Run account export/deletion and audit retrieval in the candidate namespace.
- Add production-grade retention and redaction policies for operator audit data.

