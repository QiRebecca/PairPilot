# Hackathon compliance matrix

Verified against the official All Things Agentic Hackathon pages on
2026-08-28. The binding rules and current Devpost pages—not the implementation
prompt—are the source of truth.

Official sources:

- [Overview and requirements](https://allthingsagentichackathon.devpost.com/)
- [Official rules](https://allthingsagentichackathon.devpost.com/rules)
- [FAQ](https://allthingsagentichackathon.devpost.com/details/faqs)
- [Resources and track guidance](https://allthingsagentichackathon.devpost.com/resources)
- [Current updates](https://allthingsagentichackathon.devpost.com/updates)

Status legend: **Verified**, **Implemented / positive human commit pending**,
**Pending**, or **Not applicable**. A row becomes Verified only after direct
evidence exists.

| Official requirement | Implementation evidence | Repository evidence | Google Cloud evidence | Video evidence | Status |
|---|---|---|---|---|---|
| New project built during Aug 3–31, 2026 submission period | New empty repository created 2026-08-28; root commit records origin | `PRIOR_WORK.md`; Git root commit `747bf7f` | Dedicated project `pairpilot-agentic-ecb84a` | Show repository creation/history if requested | **Verified** |
| Submit in exactly one category | Product targets the complete autonomous workflow category | README and Devpost copy will say `Taskmaster` | Run and event resources will demonstrate complete workflow | Title card identifies Taskmaster | **Verified** |
| Build a complete workflow, not merely a chatbot | One intent causes relationship lookup, discovery, A2A negotiation, deterministic cost, proposal, both agent acceptances, hold, and approval pause; atomic commit/memory growth is implemented and invariant-tested | Orchestrator, tools, policies, UI, CLI and evaluation reports | Three public Cloud Run runs + Firestore + Pub/Sub | Continuous end-to-end live run | **Implemented / positive human commit pending** |
| Use Gemini 3.5 or newer through Gemini API or Vertex AI | Authenticated Vertex AI GA `gemini-3.7-flash`; no silent fallback | `docs/MODEL_VERIFICATION.md`; pinned config | Three deployed runs include exact SDK model metadata | Accurate UI badge and Cloud logs | **Verified** |
| Use at least one Google agent framework | Google ADK 2.8.0 Qi, Alice, Maya, and Lena agents | Agent definitions; `docs/A2A_SPIKE_REPORT.md` | Public orchestrator and private peers executed live ADK turns | Live turn audit panel | **Verified** |
| Use at least one Google Cloud infrastructure service | Dedicated billed project, London Firestore Native, Vertex AI, Pub/Sub, Cloud Run, Artifact Registry, Cloud Build, IAM, Logging | Cloud/deployment reports; `infra/` scripts | Revisions, digests, logs, Firestore state and outbox verified | Console and `.run.app` proof planned | **Verified** |
| Hosted project URL if available; hosting encouraged | Public judge-facing web service without sign-in | React app, FastAPI API, multi-stage Dockerfile | Public `pairpilot-orchestrator` URL, revision `00005-lbc` | Browser address bar shows `.run.app` | **Verified** |
| Text description: features/functionality | Honest product overview and golden-path behavior | `DEVPOST_SUBMISSION.md` | Resource names referenced without secrets | Narration aligns with text | **Verified** |
| Text description: technologies used | Exact model, ADK, A2A, Firestore, Pub/Sub, Cloud Run | README and Devpost submission | Verified service inventory | Architecture and Cloud proof | **Verified** |
| Text description: other data sources | Seeded synthetic personal-agent world facts; no scraping | README data-source disclosure | Firestore seeded records | Brief disclosure | **Verified** |
| Text description: findings and learnings | Actual live-run evaluation, failures, fixes, and limitations | `docs/EVAL_REPORT.md`; Devpost copy | Run and log evidence | Closing learnings | **Verified** |
| Code repository URL | New independent repository with compatible dependencies | Public Git host URL or required private reviewer access | Not applicable | Optional repo view | **Pending** |
| Reproducible spin-up instructions | Local ADC, seed, test, deploy, reset, verify | README and Makefile | Idempotent bootstrap/deploy/reset/verify scripts | Not required | **Verified** |
| Clear architecture diagram | Browser, Cloud Run, ADK, Gemini, A2A, Firestore, Pub/Sub, logging, approval/hold, memory pipeline | `docs/architecture.mmd` and `docs/architecture.png` | Resource names map to diagram | Show diagram at end | **Verified** |
| Demonstration video | One uninterrupted real execution; no mocked/replayed events presented as live | `DEMO_SCRIPT.md`; `docs/VIDEO_EVIDENCE_PLAN.md` | Corresponding run ID in logs and Firestore | Public YouTube or Vimeo | **Pending** |
| Video no longer than four minutes | Script budget capped below 4:00 | `DEMO_SCRIPT.md` | Not applicable | Final duration check | **Pending** |
| Video covers problem and value proposition | Conference roommate coordination framed as relationship-aware action | Demo and Devpost scripts | Not applicable | 0:00–0:45 | **Pending** |
| Video demonstrates application in action | Live model-selected tools, genuine A2A messages, approval, commit | Evaluation evidence | One corresponding production run | 0:45–3:30 | **Pending** |
| Video proves backend runs on Google Cloud | Public URL, Cloud Run revision, Cloud Logging run ID, Firestore mutation | Deployment report | Console/log/resource evidence | 3:30–3:55 | **Pending** |
| Video publicly visible on YouTube or Vimeo | Final upload after recording | Submission checklist | Not applicable | Public URL | **Pending** |
| Video in English or with English subtitles | English script and captions | `DEMO_SCRIPT.md` | Not applicable | Caption inspection | **Pending** |
| Do not overstate/fake running technology | Execution mode explicitly identifies live model; reports retain failures and pending human commit | Authenticity audit, evaluation, UI badge | Direct Cloud Run, model, A2A, Firestore and log evidence | Narration uses only verified claims | **Verified** |
| Keep submission artifacts unchanged through judging | Freeze submission commit and deployment evidence; continue future work on a fork | `SUBMISSION_CHECKLIST.md` | Preserve judging revision until winners announced | Not applicable | **Pending** |
| Respect third-party IP, privacy, and acceptable-content rules | Synthetic demo identities, generated social artwork, no third-party media or private data | MIT license, third-party notices, SECURITY, source/history secret scans | Redacted logs and audited images | Video plan omits sensitive billing data | **Verified** |

## Judging alignment

| Criterion | Weight | PairPilot proof target | Status |
|---|---:|---|---|
| Innovation & Operational Utility | 40% | Autonomous relationship-aware coordination removes a messy multi-party workflow while involving the human only for irreversible commitment | **Verified to approval boundary** |
| Architectural Discipline & Tech Stack | 30% | Independent contexts, typed A2A, deterministic authority, Firestore truth, Pub/Sub outbox, least-privilege Cloud Run | **Verified** |
| Demo & Production Readiness | 30% | Continuous live Gemini demo, diagram, reproducible repo, Cloud Run/Logging/Firestore evidence | **Deployment verified; video pending** |

## Time-sensitive facts

- Submission deadline: **2026-08-31 at 5:00 PM Pacific Time**.
- Only the first four minutes of a longer video may be evaluated.
- The submission must remain substantively unchanged during the judging period.
- Promotional-credit availability does not replace the entrant's responsibility
  for charges beyond the credit amount.
