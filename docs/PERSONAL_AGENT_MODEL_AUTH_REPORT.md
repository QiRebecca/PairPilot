# Personal Agent Model Authentication Report

Date: 2026-08-30 (Asia/Shanghai)

## Candidate runtime

- Google Cloud project: `pairpilot-agentic-ecb84a`
- Region: `europe-west2`
- Candidate tag: `real-agent-chat`
- Candidate revision: `pairpilot-orchestrator-00024-nef`
- Candidate URL:
  `https://real-agent-chat---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`
- Image digest:
  `sha256:135c9fbb0b8305adeebe991c96e4150581a49e4f39889dc7f52379ef161af964`
- Runtime service account:
  `pairpilot-runtime@pairpilot-agentic-ecb84a.iam.gserviceaccount.com`
- Model: `gemini-3.7-flash`
- Model location: `global`
- Execution mode: `LIVE GEMINI + GOOGLE ADK + A2A`

## Authentication path

The server constructs the ADK `Gemini` model with project and location and uses
the Cloud Run service identity through Application Default Credentials. There
is no Gemini or Vertex API key in the frontend, image, repository, or request
body. Firebase's public browser configuration remains limited to authentication
bootstrap and is not a model credential.

The runtime service account currently has:

- `roles/aiplatform.user`
- `roles/datastore.user`
- `roles/firebaseauth.admin`
- `roles/pubsub.publisher`
- `roles/pubsub.subscriber`
- `roles/cloudtrace.agent`
- `roles/logging.logWriter`

`roles/aiplatform.user` supplies the required Vertex AI invocation permission;
the remaining roles support the existing authenticated product, persistence,
events, and observability.

## Live proof

A local ADC smoke run called the pinned model and returned:

- `message.accepted`
- `agent.started`
- streaming text deltas
- `agent.completed`
- `message_classification=FRESH_LIVE_GEMINI_RESPONSE`
- a persisted ADK session and multiple ADK events

A second live smoke run caused Gemini to select
`create_task_workspace`, created exactly one task, and produced the canonical
task conversation ID.

The final Cloud Run candidate then completed authenticated Firebase user turns.
Examples from the final run:

- User A global invocation `invocation_5b96db36ad0e602b343408be`
- User A global ADK session `adk_session_452cf7230ac9e35e0023ddcf`
- User B global invocation `invocation_fd32fce7e6ee21ab562ce9b3`
- User B global ADK session `adk_session_045568d9584bab10fb0843fe`
- User A task invocation `invocation_7a27f03ccc1dbb20345dd56e`
- User B task invocation `invocation_8b38c5eb39b56cf1367b0182`

All are persisted with model ID, execution mode, timings, token usage, tool IDs,
and successful completion status.

Cloud Logging for revision `pairpilot-orchestrator-00024-nef` records the
authenticated conversation HTTP requests. The corresponding Firestore
invocation records provide the model/session/tool correlation without logging
prompts, tokens, passwords, or Firebase ID tokens.

## Cost and secret controls

- The existing billed hackathon project and credit are used.
- Cloud Run remains min-instances 0 and can scale to zero.
- No credentials were printed by the live E2E scripts.
- `npm audit` and `pip-audit` found no known vulnerabilities.
- A diff credential-pattern scan found no private key, bearer token, or API-key
  pattern.
