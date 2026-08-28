# Intent layer deployment report

Status: **CANDIDATE DEPLOYMENT PENDING**.

## Protected production baseline

- Baseline commit: `9930444`.
- Rollback tag: `pre-intent-marketplace-9930444`.
- Orchestrator revision before correction: `pairpilot-orchestrator-00005-lbc`.
- Peer revision before correction: `pairpilot-peer-agents-00009-8l4`.
- Existing production traffic remained 100% on those verified revisions during
  local implementation.

## Candidate strategy

`infra/deploy_intent_v2.sh` builds immutable peer/orchestrator images and deploys
both existing services with `--no-traffic --tag intent-v2`. It reuses the
current project, runtime identity, registry, region, and service names. It does
not create billing resources, credentials, keys, projects, or new services.

Before any traffic change, this report will record:

| Evidence | Peer | Orchestrator |
|---|---|---|
| Candidate revision | pending | pending |
| Image digest | pending | pending |
| Tagged URL | pending | pending |
| Health/config verification | pending | pending |
| Production traffic | unchanged | unchanged |

## Migration and live gates

- [ ] tagged health, public redaction, OG asset, and service identity pass;
- [ ] idempotent reset reseeds Maya/Lena posts and leaves Qi empty;
- [ ] existing evolved data remains readable;
- [ ] live structured Qi draft uses current input;
- [ ] three fresh tagged runs reach the approval boundary within bounds;
- [ ] at least two runs use distinct valid trajectories;
- [ ] privacy and intent-scoped A2A evidence passes;
- [ ] real human positive commit passes;
- [ ] P0 checks pass before production traffic migration.

## Rollback

The old revisions remain deployable and addressable. The exact traffic command
will be filled with the verified revision name before migration; conceptually:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --region europe-west2 --to-revisions OLD_ORCHESTRATOR_REVISION=100
gcloud run services update-traffic pairpilot-peer-agents \
  --region europe-west2 --to-revisions OLD_PEER_REVISION=100
```

No production migration will be recorded until it actually occurs.
