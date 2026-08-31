# PairPilot V1 Current System Audit

Audit date: 2026-09-01 (Asia/Shanghai)

## Protected baseline

- Repository: `/Users/zhangqi/Documents/pairpilot-google-agentic`
- Starting branch: `multi-user-public-beta`
- Starting HEAD: `bf23e7b6f463d6c0d5a17d23505f9c8810cfbcf4`
- Protective tag: `pre-v1-complete-20260901`
- V1 implementation branch: `codex/pairpilot-v1-complete`
- The starting worktree contained verified but uncommitted Personal Agent Chat,
  persistent ADK session, authenticated SSE, and generic A2A changes. They were
  preserved when the V1 branch was created.

## Baseline verification

- Python: 77 tests passed; 16 dependency deprecation warnings.
- Frontend: 5 tests passed across 2 files.
- ESLint: passed with zero warnings.
- TypeScript/Vite production build: passed.
- Firestore rules deny all direct browser access; Cloud Run is the data boundary.

## Deployed Google Cloud state

- Project: `pairpilot-agentic-ecb84a`
- Region and Firestore location: `europe-west2`
- Firestore: Native mode, pessimistic concurrency.
- Runtime model: `gemini-3.7-flash`, Vertex AI through ADC.
- Runtime identity:
  `pairpilot-runtime@pairpilot-agentic-ecb84a.iam.gserviceaccount.com`
- Runtime roles include Vertex AI user, Datastore user, Firebase Auth admin,
  Pub/Sub publisher/subscriber, logging writer, and trace agent.
- Cloud Run container concurrency: 16; min instances 0; configured max instances
  20.
- Production traffic remains 100% on `pairpilot-orchestrator-00011-xeg`.
- Latest ready candidate: `pairpilot-orchestrator-00024-nef`, image digest
  `sha256:135c9fbb0b8305adeebe991c96e4150581a49e4f39889dc7f52379ef161af964`.
- Candidate tags `personal-os` and `real-agent-chat` have zero production traffic.
- The permanent `pairpilot-multi-user-worker` subscription still targets the
  older `multi-user-beta` tag/revision family, not the latest candidate.
- There is one Pub/Sub topic, `pairpilot-events`.
- There is no dead-letter topic on the push worker subscription.
- No Cloud Scheduler reconciliation job was found.

## Current authenticated production architecture

The authenticated `/app` path has real Firebase email authentication, one
generic Personal Agent record per Firebase UID, owner-scoped global and task
conversations, Firestore-backed ADK sessions/events, live Gemini tool use,
authenticated SSE, task/Post state, generic user-owned A2A, dual human approval,
Rooms, blocking, reporting, export, and deletion.

The primary implementation is split across:

- `multi_user_platform.py`: account, task, Post, approval, Room, safety, export,
  deletion, and bootstrap authority;
- `personal_agent_chat.py`: global/task tools and real live Agent turns;
- `firestore_session_service.py`: persistent ADK sessions and events;
- `multi_user_agent.py`: persistent two-sided A2A turns;
- `generic_agent_runtime.py`: current single-pair discovery/proposal runtime;
- `web.py`: authenticated APIs, SSE, and Pub/Sub worker;
- `BetaApp.tsx`: authenticated product shell.

## Verified strengths

1. Firebase ID tokens are verified server-side and request bodies cannot choose
   the authoritative UID.
2. Canonical conversation IDs are owner-scoped:
   `user:{uid}:global` and `user:{uid}:task:{task_id}`.
3. Successful Agent replies persist model, session, invocation, tool, token,
   timing, and classification provenance.
4. Model failure returns `agent.error` and does not save a fabricated assistant
   answer.
5. Publishing requires explicit current user authority.
6. Generic A2A runs both user-owned Agents live and rejects missing fresh Agent
   messages.
7. The first human approval cannot commit a Match; the second matching approval
   commits through the authority layer.
8. Cross-user conversation/audit access returns 403 in automated and live tests.
9. Public Post projections omit login email and owner-private intent data.
10. Synthetic demo users are namespace-separated from authenticated production
    data.

## V1-critical gaps

### Domain and community

- No first-class Community, membership, invite, moderator, or community-scoped
  discovery entities exist.
- Onboarding does not collect communities, notification preferences, or complete
  autonomy/visibility choices.
- Only ROOM_SHARE has meaningful matching fields; other V1 intent types are not
  represented by frozen typed policies.

### Candidate Pool and ranking

- The automatic worker selects the first compatible candidate and returns.
- It does not maintain up to five contacts or three simultaneous negotiations.
- Candidate assessments do not implement the frozen state/rank/evidence schema.
- No immutable rank-change event records previous/new ordering and evidence IDs.
- The authenticated UI has no complete Candidates or Agent Rooms task tabs.
- Primary and backup choices are not maintained.

### Continuous background operation

- Only a small event set is consumed.
- New/updated/paused/resumed/closed/expired/matched Post lifecycle events are not
  all implemented.
- No periodic reconciliation handles missed events, stale holds, expiry, failed
  jobs, or availability.
- No dead-letter queue or recovery UI exists.
- The current permanent worker subscription does not point at the newest code.

### Memory and relationships

- The current context filter checks archive/scope but not the required Memory
  lifecycle status. A `PROPOSED` or `REVIEWABLE` Memory can influence a future
  turn before confirmation.
- The authenticated Memory page is read-only and lacks confirm/edit/reject/archive/
  restrict/delete actions.
- Working beliefs are not explicitly separated from long-term Memory.
- Relationship records are thin and the authenticated Network page does not show
  provenance, context, path, or reliability dimensions.
- No scheduled outcome check-in feeds authoritative relationship evidence.

### Rooms, decisions, contacts, and notifications

- Candidate negotiation Rooms are not consistently created for every candidate.
- The authenticated Request page exposes approval but lacks a complete rejection,
  counterproposal, keep-backup, and revalidation interaction model.
- No Match-scoped opt-in Contact Card exists.
- No unified in-app Notification entity/page or preference enforcement exists.
- Presentation directives are persisted but the authenticated chat does not yet
  render all allowlisted authoritative cards.

### Safety, abuse, administration, and analytics

- Basic block/report/rate-limit/quota controls exist, but IP-hash, task, and
  recipient-Agent rate limiting are incomplete.
- Blocking is not yet proven across every pending Room/negotiation/message state.
- There is no authenticated role-claimed `/admin` console.
- No moderation, failed-job, DLQ, usage, deletion, or health operations dashboard
  exists.
- Product analytics events and the required aggregate dashboard are absent.

### Reliability and scale

- No five-user multi-candidate live acceptance exists.
- No 20–50 authenticated-user infrastructure smoke result exists.
- Worker crash/lease-expiry, dead-letter recovery, transaction-conflict, cold-start,
  and full duplicate-delivery gates are not recorded for V1.
- The current candidate is zero traffic and production still serves older code.

## Fixed-name and demo assumptions

Qi/Maya/Lena/Alice code, fixed routes, and seeded world facts remain in the
synthetic `/demo` implementation, peer-agent spike service, older `App.tsx`, and
demo tests. They are not acceptable dependencies for authenticated V1.

The authenticated `/app` path uses generic UID-derived Agent IDs. V1 work must
continue moving named code behind an explicit demo boundary and prevent future
production imports from depending on it.

## Migration strategy

1. Preserve existing production documents and add V1 fields/collections
   additively with a schema version.
2. Build first-class Communities, memberships, notifications, candidate rank
   events, jobs, contact offers, outcomes, analytics, and admin-role resources.
3. Replace single-pair discovery with an idempotent Candidate Pool coordinator.
4. Expand the Pub/Sub event contract and deploy a dedicated current worker with
   DLQ plus periodic reconciliation.
5. Enforce `Memory.status == CONFIRMED` for unrelated planning and A2A context.
6. Extend the authenticated UI; do not promote the older synthetic OS pages.
7. Deploy every phase as a zero-traffic candidate, then run independent Firebase
   users before promotion.

