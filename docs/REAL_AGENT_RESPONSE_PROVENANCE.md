# Real Personal Agent Response Provenance

Date: 2026-08-30 (Asia/Shanghai)

## Result

The authenticated `/app` product no longer creates decorative Personal Agent
answers from frontend text, keyword routing, or a deterministic backend template.
Its primary path is now:

`Firebase user -> persistent conversation -> authenticated SSE request -> Google
ADK Runner -> Vertex AI Gemini -> typed tool(s) -> persisted assistant message`

The synthetic `/demo` product remains intentionally separate and labelled.

## Durable identities and sessions

- Global conversation: `user:{uid}:global`
- Task conversation: `user:{uid}:task:{task_id}`
- Human-Agent ADK session: stable hash of owner UID and conversation ID
- A2A ADK session: stable hash of acting Agent, own intent, and peer intent
- ADK session state is stored in `adk_sessions`; non-partial ADK events are stored
  in `adk_session_events`.
- Firebase UID ownership is checked before message submission, replay, stop, and
  audit access.

Legacy global conversations are excluded from the authenticated bootstrap when
the canonical global conversation exists. Existing data is preserved for
rollback and migration evidence.

## Streaming contract

`POST /api/v1/conversations/{conversation_id}/messages` produces durable SSE
events:

- `message.accepted`
- `agent.started`
- `agent.text.delta`
- `tool.started`
- `tool.completed`
- `ui.directive`
- `agent.completed`
- `agent.error`

Each client message has an owner-scoped idempotency record. A duplicate
`client_message_id` replays stored events and does not run the model again.
`GET /api/v1/conversations/{conversation_id}/events` supports reconnect from an
event sequence, and `POST /api/v1/invocations/{id}/stop` requests cancellation.

## Persisted proof for every successful assistant message

Every successful authenticated assistant message stores:

- `assistant_message_id`
- `owner_uid`
- `personal_agent_id`
- `conversation_id`
- `task_id` when applicable
- `adk_session_id`
- `adk_invocation_id`
- `model_id`
- `execution_mode`
- `started_at` and `completed_at`
- `latency_ms`
- input and output token counts when provided by Vertex AI
- `tool_call_ids`
- `presentation_directive_ids`
- `error_status`
- `message_classification=FRESH_LIVE_GEMINI_RESPONSE`

Tool arguments/results are stored separately in `agent_tool_calls`. The
authorized audit endpoint returns messages, invocations, tools, directives, and
task-linked A2A turns without returning hidden reasoning.

The UI's live model badge is derived from the latest persisted message whose
classification is `FRESH_LIVE_GEMINI_RESPONSE`; it is not a static claim.

## Honest failure behavior

No canned assistant message is written when Vertex AI, ADK, tool execution, or
transport fails. The invocation becomes `FAILED`, the stream returns
`agent.error`, and the UI states that no assistant answer was fabricated or
saved. It offers retry as a new idempotent turn.

`test_model_failure_stream_is_honest_and_saves_no_assistant` injects a failing
model transport and verifies that:

- `agent.error` is returned;
- internal exception text is not exposed;
- no `PERSONAL_AGENT` message is persisted.

The production Agent-to-Agent negotiation path also rejects missing fresh Agent
messages. The former fixed source/target room replies were removed.

## Live conversational acceptance

`scripts/run_live_conversation_acceptance.py` ran against
`gemini-3.7-flash` using ADC and passed:

| Test | Live result |
| --- | --- |
| A — arbitrary task | Fresh invocation asked a contextual clarification; no ICML template was required. |
| B — follow-up memory | Reused `adk_session_f1284497d5ae321897560ea8` and recalled quiet nights. |
| C — task modification | Selected `revise_intent_post`; persisted the $45 limit. |
| D — status | Selected `inspect_task_status` and read authoritative state. |
| E — UI control | Selected `inspect_candidate_assessments` and `show_candidate_comparison`; emitted one directive. |
| F — private instruction | Selected both private-instruction and scoped-A2A tools; the private reason was absent from outbound text. |
| G — separate user | Used a different UID and ADK session; no User A context appeared. |
| H — restore/replay | Live candidate refresh restored stored messages; unit coverage proved duplicate submission replays without another model call. |

## Verification

- Backend: 77 tests passed.
- Frontend: 5 tests passed across 2 test files; lint and production build passed.
- TypeScript build: passed.
- ESLint: passed with zero warnings.
- Explicit live text stream: passed.
- Explicit live model-selected task tool: passed.
- Live A-G conversation suite: passed.
- Live two-user Firebase/ADK/A2A/dual-approval suite: passed.
- `npm audit --omit=dev`: zero known vulnerabilities.
- `pip-audit`: zero known vulnerabilities.
- Diff credential-pattern scan: no match.
- Final candidate landing page DOM and visual screenshot: passed. The candidate
  browser session was signed out, so no authenticated screenshot is claimed;
  authenticated behavior was verified through the live Firebase E2E and frontend
  tests.

No hidden chain-of-thought is persisted or exposed.
