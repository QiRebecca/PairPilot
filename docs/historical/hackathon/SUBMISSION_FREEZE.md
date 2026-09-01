# PairPilot Submission Freeze

Freeze target: Google All Things Agentic Hackathon, Taskmaster track

Freeze date: 2026-09-01 (Asia/Shanghai)

## Frozen product definition

PairPilot is an agent-operated marketplace for real-world plans. Every user
owns a persistent Personal Agent that turns ordinary conversation into a
privacy-aware Post, continuously monitors other active Posts, communicates with
multiple Personal Agents, dynamically ranks candidates, and completes a Match
only after both humans approve.

After the final tagged commit, allowed changes are limited to a production
outage, a submission-blocking navigation/state/publication defect, an
authorization or privacy defect, or incorrect submission documentation. Do not
add navigation, task types, social features, models, themes, authentication
providers, projects or experimental architecture during judging.

## Runtime lock

| Item | Frozen value |
| --- | --- |
| Production URL | <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/> |
| Google Cloud project | `pairpilot-agentic-ecb84a` |
| Region | `europe-west2` |
| Firestore | Native `(default)`, `europe-west2` |
| Runtime service account | `pairpilot-runtime@pairpilot-agentic-ecb84a.iam.gserviceaccount.com` |
| Model | `gemini-3.7-flash` |
| Production orchestrator | `pairpilot-orchestrator-00045-tig` (100%; tag `submission-prod`) |
| Final orchestrator digest | `sha256:4aded86e939fe18e8beffa9d9a1a2ee731436cb8509c6d5631252e7123e2fb1a` |
| Orchestrator runtime | timeout 180 seconds; max instances 20; concurrency 16; min instances 0 |
| Rollback orchestrator | `pairpilot-orchestrator-00039-joh` |
| Peer Agent revision | `pairpilot-peer-agents-00022-seh` (100%) |
| Peer Agent digest | `sha256:bfe8e9477136f848db5e3eb6af14d6fe1982f56f0a5723a5c7964120f5f12b70` |
| Final Git commit | `PENDING_FINAL_COMMIT` |
| Submission branch | `hackathon-submission-freeze` — `PENDING_CREATION` |
| Submission tag | `all-things-agentic-submission-v1` — `PENDING_CREATION` |

The commit/branch/tag placeholders must be replaced only after the worktree is
clean and the final QA, secret scans and dependency audits pass. Do not tag an
uncommitted or partially verified state.

## Background infrastructure

| Resource | Frozen value |
| --- | --- |
| Event topic | `projects/pairpilot-agentic-ecb84a/topics/pairpilot-events` |
| Dead-letter topic | `projects/pairpilot-agentic-ecb84a/topics/pairpilot-events-dead-letter` |
| Worker subscription | `pairpilot-multi-user-worker` |
| Worker endpoint | `https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/api/internal/events` |
| Dead-letter attempts | 5 |
| Audit subscription | `pairpilot-events-audit` |
| DLQ inspection subscription | `pairpilot-events-dead-letter-inspection` |
| Reconciliation | Authenticated Cloud Scheduler call every five minutes |

The canonical production host is the only worker push target. No obsolete
revision should receive event jobs.

## Freeze acceptance snapshot

- Final judge requester cohort: 3 candidates, 6 rooms,
  1 match, 1 relationship and 1 confirmed memory.
- Persistent chat gate: two consecutive task-focused turns in one global chat,
  PASS.
- Production health concurrency: 60/60 HTTP 200.
- Final local regression: 100 backend/integration tests (including live A2A),
  6 frontend tests, Ruff, ESLint, TypeScript and the production build passed.
- Strict Python mypy still reports 8 pre-existing ADK/Peer typing errors. It is
  explicitly not recorded as a passing gate.
- Source/history secret scans, npm/Python dependency audits and the 1440×900
  integrated browser path passed. Video recording and final human Devpost submit
  remain pending as recorded in `docs/FINAL_SUBMISSION_QA.md`.

## Rollback

The immediate pre-candidate production orchestrator remains available as
`pairpilot-orchestrator-00039-joh`. The earlier V1 cut
`pairpilot-orchestrator-00035-beq` also remains available. The frozen Peer
revision is unchanged.

Rollback only the orchestrator:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a \
  --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00039-joh=100
```

Restore the frozen integrated revision:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a \
  --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00045-tig=100
```

If the Peer service itself is unavailable, first investigate `00022-seh` logs;
do not roll it independently without rerunning direct A2A and dual-approval
smoke tests.

## Operational rule during judging

1. Do not change traffic after submission while production is healthy.
2. If production is unavailable, capture the failing health response and Cloud
   Logging evidence before rollback when practical.
3. Roll back only the affected service to the explicit revision above.
4. Run sign-in, one live chat turn, Explore, A2A and Match-read smoke checks.
5. Record the incident and exact commands in the submission handoff.
6. Never reset global Firestore data; reset only the controlled judge workspace.

## Final freeze checklist

- [ ] Replace `PENDING_FINAL_COMMIT` with `git rev-parse HEAD`.
- [ ] Confirm `git status --short` is empty.
- [ ] Record exact final test counts and audit output.
- [ ] Complete source and Git-history secret scans.
- [ ] Confirm no `.env`, credential, token, private email, test password or
  service-account JSON is tracked.
- [ ] Create `hackathon-submission-freeze` from the verified commit.
- [ ] Create annotated tag `all-things-agentic-submission-v1` at that commit.
- [ ] Push the branch and tag, then verify the repository while signed out.
- [ ] Create `post-hackathon-development` only after the submission tag exists.
- [ ] Do not route traffic again unless production is unavailable.
