# PairPilot real Personal Agent chat audit

Audit date: 2026-08-30  
Audited baseline: commit `bf23e7b` on `multi-user-public-beta`  
Scope: authenticated `/app/*` product, legacy `/demo`, background multi-user Agent turns

## Gate result before remediation

**FAIL — the authenticated product is form-driven, not conversation-driven.**

The deployed multi-user platform has real Firebase identity, isolated state,
real background ADK/Gemini negotiation turns and dual approval. However, the
primary authenticated “My Agent” input does not invoke Gemini or ADK. It posts
structured form values directly to a deterministic task-creation endpoint.
The backend then persists a hardcoded `PERSONAL_AGENT` message even though no
Personal Agent turn occurred.

No Gemini or Google API key is present in frontend product code. Firebase's
browser API key is non-secret Firebase client configuration used only for
Firebase Authentication. Existing server-side Gemini clients use Vertex AI,
the Cloud Run service account and Application Default Credentials; that path
must be preserved.

## Exact authenticated path: “Tell your Personal Agent what you need”

| Stage | Exact source | Behavior |
|---|---|---|
| Route selection | `web/src/RootApp.tsx:7-15` | `/app/*` selects `BetaApp`; it does not select the legacy chat app. |
| Visible composer | `web/src/BetaApp.tsx:45-50` | Captures `goal`, event, location, dates and comma-separated requirements in a required form. |
| Submit handler | `web/src/BetaApp.tsx:48` | Calls `POST /api/app/tasks` with `CreateUserTaskInput`, then refreshes bootstrap and navigates to the task page. No streaming connection exists. |
| Fresh ID token | `web/src/auth.tsx:132-137` | Calls Firebase `getIdToken(true)` and adds it to the protected request. |
| Firebase verification | `services/orchestrator/pairpilot_orchestrator/auth/dependencies.py:29-46` | Extracts the Bearer token and delegates verification. |
| Revocation/disabled check | `services/orchestrator/pairpilot_orchestrator/auth/firebase_auth.py:30-49` | Firebase Admin verifies the token with `check_revoked=True` through Cloud Run ADC and derives the principal UID. |
| API route | `services/orchestrator/pairpilot_orchestrator/web.py:545-562` | Calls `create_user_task`; Gemini and ADK are not invoked. |
| Persistence | `services/orchestrator/pairpilot_orchestrator/multi_user_platform.py:511-651` | Atomically creates task, private intent, task conversation, user message, review decision and a deterministic Agent message. |
| Fabricated Agent text | `services/orchestrator/pairpilot_orchestrator/multi_user_platform.py:608-623` | Persists “I created an isolated request…” with role `PERSONAL_AGENT`, although no model invocation or tool call exists. |
| Displayed result | `web/src/BetaApp.tsx:58-65` | Shows form-derived task/post/decision state. It does not render a persistent global or task chat transcript. |

Request body at the audited boundary:

```json
{
  "title": "<event> coordination",
  "task_type": "peer_coordination",
  "goal": "<free text plus required form context>",
  "event": "<required>",
  "location": "<required>",
  "date_start": "YYYY-MM-DD",
  "date_end": "YYYY-MM-DD",
  "public_requirements": [],
  "maximum_additional_cost_usd": 0,
  "partial_date_overlap_allowed": true
}
```

Principal: verified Firebase UID.  
Conversation ID: deterministic `stable_id("conversation_task", task_id)` is
created only after form submission.  
ADK session ID: none.  
Gemini invoked: no.  
ADK invoked: no.  
Tools available: no.  
Response persisted: deterministic task and message records are persisted.  
Output streamed: no.  
Fallback: the deterministic path is the only path.

## Other visible Agent-labelled paths

### Authenticated Coordination Room messages

- Source: `multi_user_agent.py:73-189`, invoked from the authenticated Pub/Sub
  worker in `web.py`.
- Classification: **A, fresh live Gemini response**, when negotiation succeeds.
- Model/runtime: Google ADK `Runner`, Vertex AI `Gemini`, configured model ID,
  `enterprise=True`, project and location from server settings/ADC.
- Persistence: selected peer text is stored in `room_messages` by
  `generic_agent_runtime.py`.
- Session: a new `InMemorySessionService` and random session ID are created for
  every turn (`multi_user_agent.py:107-153`).
- Tools: none; structured acceptance output only.
- Streaming to user: no; background result appears after bootstrap refresh.
- Provenance gap: room-message provenance names the generic runtime but omits
  ADK session/invocation IDs, model metadata, tokens and timing.

### Legacy `/demo` “Message Qi” path

- Frontend: `web/src/App.tsx:80` posts to `/api/os/messages`.
- Endpoint: `web.py:1067-1189`; it is a synthetic demo route, not the
  authenticated multi-user product.
- The route persists user text, invokes the typed router, then executes fixed
  Python branches based on structured intent and persists `routing.response_text`.
- `personal_agent_routing.py:18-60` does invoke a fresh ADK/Gemini turn, but it
  creates a new in-memory session and the fixed `qi-owner` on every message.
- Tools are not supplied to the ADK Agent. Python interprets the typed routing
  result and runs product actions afterward.
- Output is returned as one JSON response, not streamed.
- The demo frontend contains static welcome/online/product language and is
  correctly labeled synthetic. It cannot satisfy the real-user gate.

### Form/status/notice text in authenticated UI

Examples at `BetaApp.tsx:50-65` such as “Your Agent creates…”, “Published. Your
Agent is now looking…” and proposal notices are **D, frontend template text**.
They may accurately summarize deterministic state, but they are not Agent
responses and must never carry a live-response badge.

## Failure-mode audit

| # | Finding | Severity | Evidence / required correction |
|---|---|---|---|
| 1 | “Message Agent” only creates Firestore records | **Critical** | Authenticated composer calls `/api/app/tasks`, not a conversation endpoint. Replace primary path with an authenticated live turn. |
| 2 | Chat input is a required post/task form | **Critical** | Event/location/dates are mandatory before any response. Make arbitrary chat primary; forms become Agent-created editors. |
| 3 | Follow-ups do not exist in authenticated app | **Critical** | No global/task submit handler or conversation API exists. |
| 4 | Agent-labelled response is deterministic | **Critical** | `create_user_task` writes a canned `PERSONAL_AGENT` message without an invocation. Remove this fabrication. |
| 5 | Legacy model acts only as a router; Python performs semantic actions | **High** | No ADK tools are supplied. Implement typed authorized tools selected by the model. |
| 6 | Frontend constructs Agent-sounding notices | **High** | Keep notices as system/UI state and label them accordingly; never mix them into Agent transcript. |
| 7 | Status summaries do not invoke Gemini | **High** | Authenticated UI reads bootstrap state directly. Add state-grounded live Agent tools for status questions. |
| 8 | Every current Agent turn is stateless | **Critical** | Both legacy chat and multi-user negotiation create random in-memory sessions per turn. Implement persistent UID/conversation-bound ADK sessions. |
| 9 | Global/task context controls are not implemented for live turns | **High** | Conversation records exist but no live runtime consumes their scoped context. |
| 10 | Model claims are not bound to successful tool results | **Critical** | Canned create text is persisted without a tool call. Render action claims only after persisted tool results. |
| 11 | User-facing tool explanations are hardcoded | **High** | Existing create/publish notices are deterministic and not model-generated after a tool result. |
| 12 | No explicit chat failure record or retry | **Critical** | There is no authenticated chat invocation record. Model failures cannot be restored/audited. |
| 13 | Fixed Qi/Maya/Lena/Alice logic remains | **Medium** | It remains in `/demo` and earlier engine paths. It is acceptable only while unreachable from authenticated chat. |
| 14 | Real background peers use generic runtime but no persistent sessions | **High** | Arbitrary Agent loading exists; session/provenance must be made persistent and peer turns recorded separately. |
| 15 | Live/online labels are not invocation-derived | **High** | UI shell labels Agent online without current invocation metadata; add a persisted invocation-derived badge. |

## Classification inventory

- **A — fresh live Gemini:** background two-Agent negotiation messages;
  legacy demo router responses.
- **B — stored previous Gemini:** stored room messages produced by the previous
  background turn; no complete invocation provenance is attached.
- **C — deterministic system text:** task creation Agent message and backend
  lifecycle notices.
- **D — frontend template text:** welcome text, online label, publication and
  approval notices.
- **E — manually entered user content:** task `goal`, room human messages and
  form-edited public post fields.
- **F — synthetic demo:** all named Qi/Maya/Lena/Alice UI and `/api/os/*`
  conversation behavior.

## Remediation order

1. Remove the fake Agent message from deterministic task creation.
2. Add persistent Firestore-backed Google ADK Sessions keyed by the verified
   UID and authoritative conversation.
3. Add typed, owner-authorized global/task tools and a generic Agent factory.
4. Add an idempotent authenticated streaming API and persisted invocation
   provenance, with honest failures and no canned fallback.
5. Make the existing global/task conversation UI primary and forms optional.
6. Extend Pub/Sub peer turns to the same persistent runtime/provenance model.
7. Run live conversational and two-user acceptance gates before deploying the
   `real-agent-chat` zero-traffic tag.
