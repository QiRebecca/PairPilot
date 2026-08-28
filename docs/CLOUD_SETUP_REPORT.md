# Google Cloud setup report

Verified on 2026-08-28. This report intentionally omits the billing-account ID,
credit code, authentication credentials, and billing-console URL.

## Project

| Item | Verified value |
|---|---|
| Project ID | `pairpilot-agentic-ecb84a` |
| Display name | `PairPilot Agentic Hackathon` |
| Authenticated principal | Project creator account (email omitted from public report) |
| Billing linkage | Enabled on the intended open billing account |
| Promotional credit | Visible, active, and 100% remaining at verification time |
| Local authentication | gcloud user login and Application Default Credentials |
| ADC quota project | `pairpilot-agentic-ecb84a` |

Two other billing accounts visible to the principal were closed. The project was
linked only after the intended account and its active hackathon credit had been
confirmed in the authenticated Cloud Console.

## Budget guardrail

| Item | Verified value |
|---|---|
| Budget ID | `dfe7f831-ce82-4979-8441-2d7f2470d926` |
| Display name | `PairPilot Hackathon Safety Budget` |
| Amount | GBP 90 |
| Scope | Only project `pairpilot-agentic-ecb84a` |
| Period | 2026-08-25 through 2026-10-24 |
| Thresholds | 50%, 80%, 90%, 100% of current spend |
| Credit treatment | Exclude all credits (gross-usage alerting) |
| Default IAM recipients | Enabled |
| Automatic shutdown | Disabled |

The amount leaves a margin below the promotional-credit value. Production will
use Cloud Run minimum instances 0, maximum instances 1 or 2, bounded model
turns, output tokens, retries, and wall-clock time.

## Regions and data

- Vertex AI model endpoint: `global`.
- Cloud Run and Artifact Registry deployment region: `europe-west2` (London).
- Firestore database: Native mode, Standard edition, `europe-west2`.
- Pub/Sub: global service with project-scoped topics and authenticated push.

The Firestore location was verified as supported before database creation.
See `docs/CLOUD_REGION_DECISION.md` for the rationale.

## Runtime identity

User-managed service account:

```text
pairpilot-runtime@pairpilot-agentic-ecb84a.iam.gserviceaccount.com
```

Project roles granted:

- `roles/aiplatform.user`
- `roles/datastore.user`
- `roles/pubsub.publisher`
- `roles/pubsub.subscriber`
- `roles/logging.logWriter`
- `roles/cloudtrace.agent`

No Owner, Editor, API-key, service-account key, or Secret Manager access role
was granted. Cloud Run invocation grants will be applied only to the services
that need them during deployment.

## Enabled service APIs

Required APIs verified enabled include Vertex AI, Cloud Run, Firestore,
Pub/Sub, Artifact Registry, Cloud Build, Secret Manager, Cloud Logging, Cloud
Trace, IAM Credentials, Cloud Resource Manager, Service Usage, Cloud Billing,
and Cloud Billing Budgets. Google Cloud also enabled service dependencies such
as IAM, Monitoring, Storage, and Datastore.

## Verification commands

Non-secret command families used:

```bash
gcloud --version
gcloud auth list
gcloud config list
gcloud billing accounts list
gcloud billing projects describe "$PROJECT_ID"
gcloud billing budgets create ...
gcloud services list --enabled
gcloud firestore databases describe --database='(default)'
gcloud projects get-iam-policy "$PROJECT_ID"
```

The installed CLI was Google Cloud SDK 582.0.0. Authentication tokens and ADC
files are local-only and excluded from Git.

