# PairPilot Final Submission QA

QA cut: 2026-09-01 (Asia/Shanghai)

Status vocabulary:

- **PASS**: completed with recorded evidence.
- **PENDING FINAL FREEZE RUN**: must be rerun on the exact final commit; earlier
  evidence is listed but is not silently treated as proof of new code.
- **KNOWN PRE-EXISTING FINDING**: observed and disclosed, but not represented as
  a passing gate.
- **HUMAN**: depends on human login, recording, upload or final submission.

## Final-candidate deployment

| Check | Status | Evidence |
| --- | --- | --- |
| Production URL responds | PASS | <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/> |
| Production orchestrator | PASS | `pairpilot-orchestrator-00045-tig` is Ready and serves 100%; digest `sha256:4aded86e939fe18e8beffa9d9a1a2ee731436cb8509c6d5631252e7123e2fb1a` |
| Orchestrator runtime limits | PASS | Timeout 180 seconds; max instances 20; concurrency 16; min instances 0 |
| Rollback revision | PASS | `pairpilot-orchestrator-00039-joh` remains available |
| Peer Agent traffic | PASS | `pairpilot-peer-agents-00022-seh`, 100% |
| Exact model/runtime | PASS | `gemini-3.7-flash`; `LIVE GEMINI + GOOGLE ADK + A2A` |
| Firestore | PASS | Native database `(default)` in `europe-west2` |
| Authenticated background worker | PASS | `pairpilot-multi-user-worker` pushes to production `/api/internal/events` with a five-attempt DLQ policy |
| Revision startup readiness | PASS | `00042-rob` deployed successfully in 13.5 seconds and became container healthy in 10.02 seconds |
| End-to-end cold-start sign-in/chat | PENDING FINAL FREEZE RUN | Run once after the service has scaled to zero; record user-visible latency and successful `agent.completed` |
| Production concurrency | PASS | 60/60 health requests returned HTTP 200 |

## Final integrated product path

| Product assertion | Status | Current evidence |
| --- | --- | --- |
| One persistent Personal Agent chat | PASS | Two consecutive task-focused live turns completed in the same global conversation |
| Chat-created Task and Agent-drafted Post | PASS | Live V1 gates; persisted task, private draft and tool provenance |
| Draft survives navigation | PENDING FINAL FREEZE RUN | The integrated UI reads/writes the authoritative private draft; final browser navigate-away/back proof is still required |
| Approve & Publish persists | PASS | Authenticated publication produces an `OPEN` `intent_posts` record and survives bootstrap refresh |
| Published Post and Explore detail | PASS | 1440×900 production run opened the filtered Candidate B Post and full public detail panel; private canary was absent |
| Search and tags | PASS | 1440×900 production search for `A2A protocols` narrowed Explore to the correct controlled Post |
| Multiple A2A candidates and rooms | PASS | Judge requester cohort: 3 candidates, 5 private Agent/negotiation rooms and 1 Shared Room |
| Dynamic ranking | PASS | `candidate_rank_events` live evidence; four rank changes in V1 acceptance |
| Private instruction boundary | PASS | Unique canaries absent from public/A2A output in every V1 multi-intent run |
| Dual human approval | PASS | First approval waits; second commits; 15/15 matches in V1 live acceptance |
| Match and Shared Room | PASS | Judge requester: 1 completed Match and Shared Room with two Agent messages plus one labelled controlled-human message; V1: 15 matches |
| Network | PASS | Judge requester: Candidate A named relationship with atomic-Match provenance |
| Memory | PASS | Judge requester: 1 confirmed memory; proposed memory excluded before confirmation |
| Communities | PASS | Membership and community-scoped Explore are authoritative; current controlled account has memberships |

The current cohort is controlled test data. It must be labelled “Controlled
test account”, “Demo participant”, or “simulated tester” anywhere a judge could
mistake it for organic usage.

## Automated quality gates

| Gate | Final-candidate status | Most recent recorded evidence | Freeze command |
| --- | --- | --- | --- |
| Backend/integration tests | PASS | Final local regression: 100 passed, including live A2A integration | `uv run pytest` |
| Python lint | PASS | Final local regression: Ruff passed | `uv run ruff check .` |
| Frontend tests | PASS | Final local regression: 6 passed | `cd web && npm test -- --run` |
| Frontend lint | PASS | Final local regression: ESLint passed | `cd web && npm run lint` |
| TypeScript check | PASS | Final local regression passed | `cd web && npm run typecheck` |
| Frontend production build | PASS | Final local regression passed | `cd web && npm run build` |
| Strict Python mypy | KNOWN PRE-EXISTING FINDING | 8 existing ADK/Peer typing errors remain; do not describe `make typecheck` as passing | `.venv/bin/mypy --strict packages/schemas services/orchestrator services/peer_agents` |
| Live Gemini chat | PASS | Two consecutive task-focused turns completed; no `agent.error` | `scripts/verify_qi_persistent_chat.py` with secrets supplied only by environment |
| Live A2A | PASS | Production Peer Agent Cards and three JSON-RPC calls returned HTTP 200 | See `docs/V1_LIVE_ACCEPTANCE_REPORT.md` |
| Multi-user authorization | PASS | Cross-user private task/conversation reads returned HTTP 403 | V1 multi-intent acceptance scripts |
| Post publish / Explore persistence | PASS | Browser/API exposed a missing owner-only `task_id` linkage; final blocker fix now has a dedicated unit assertion and will be rechecked on the final revision | Final 1440×900 browser run plus `test_two_users_receive_isolated_private_bootstraps_and_real_posts` |
| Navigation | PASS | 1440×900 production run: My Agent request card navigated to its task; Explore detail, Rooms, Matches, Network, Memory and Communities loaded | Final browser run |
| Dual approval | PASS | Judge Requester first approval is `WAITING_FOR_OTHER_HUMAN`; Candidate A independently sees the exact v1 contract and approval button; it was intentionally not consumed | `scripts/seed_judge_cohort.py` plus final browser run |
| Memory lifecycle | PASS | Proposed memory excluded; confirmed memory retrieved | V1 multi-intent acceptance scripts |
| Pub/Sub background work | PASS | Production push HTTP 200; later Post triggered offline discovery in V1 | Pub/Sub + reconciliation inspection |
| Source secret scan | PASS | Tracked files scanned for Google API keys, private-key headers, service-account identifiers and private-key IDs; no match. Private judge guide is verified ignored/untracked | `git ls-files -z \| xargs -0 rg ...` plus `git check-ignore` |
| Git-history secret scan | PASS | Full patch history scanned for the same credential patterns; no match | `git log -p --all -- . ':!*.lock' \| rg ...` |
| npm dependency audit | PASS | 0 known vulnerabilities across production dependencies | `cd web && npm audit --omit=dev --json` |
| Python dependency audit | PASS | 0 known vulnerabilities in the frozen exported production requirements | `uv export --frozen --no-dev ...` then `uvx pip-audit --no-deps --disable-pip -r ...` |

Do not convert a pending row to PASS without pasting its exact command, result,
test count and final commit into the freeze handoff. A finite QA suite establishes
that no known exercised failure remains; it cannot prove that software has zero
possible bugs.

## Required 1440×900 browser path

Run this once on the final tagged build without editing production data outside
the controlled cohort:

1. Sign in to the prepared pre-populated requester account.
2. Open **My Agent** and confirm earlier messages remain in the one composer.
3. Open an inline request/Post card; confirm the task context opens and the same
   chat history remains.
4. Edit the draft, navigate away and back, and confirm the draft is preserved.
5. Publish a controlled draft or inspect the already-published Post; refresh and
   verify authoritative status.
6. Open **Explore**, search/filter, open a candidate Post detail and return.
7. Open ranked candidates and at least two distinct Agent Room transcripts.
8. Open the approval flow. Confirm first-human waiting state, then switch to the
   prepared candidate account and approve the same version.
9. Return to the requester; inspect Match, Shared Room, Network and Memory.
10. Open `/api/health`, then the Cloud Run revision and a redacted invocation log.

Expected time: 8–12 minutes for the full judge path; the edited demo path is
3:40–3:55.

## Visual and privacy sign-off

- [x] Browser viewport is exactly 1440×900.
- [ ] No real email, password, token, cookie, UID, phone number or private
  instruction is visible.
- [x] Controlled identities are visibly labelled.
- [ ] No developer console errors occur on the recorded path.
- [x] Cards are keyboard-focusable and the demonstrated My Agent/Explore/Room clicks navigate.
- [ ] Reload does not lose chat, Post, Match, Room, Network or Memory state.
- [ ] The video shows the model/provenance badge without exposing hidden prompts.
- [ ] Actual video timestamps replace all **planned** values in the evidence index.

## Human-only completion

- Record and review the final video.
- Upload it publicly to YouTube or Vimeo.
- Paste the video URL and private judge credentials into Devpost.
- Review team membership and click **Submit**.
