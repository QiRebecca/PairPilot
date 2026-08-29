# Submission checklist

## Required product evidence

- [x] Two distinct Firebase UIDs and persistent Personal Agents
- [x] Cross-user private task IDOR returns 403
- [x] Two public posts, two Agent acceptances and two effect contracts
- [x] First human approval waits; second commits exactly once
- [x] Shared-room membership and independent relationship projections
- [x] Zero-traffic `multi-user-beta` candidate
- [x] Final candidate `00020-vig` passes the repeatable authenticated E2E
- [x] Synthetic demo excludes production tasks and rejects production resource IDs
- [x] Direct unauthenticated Firestore access returns 403
- [ ] Provider-delivered verification and reset links tested while signed out
- [ ] Same-browser A→sign-out→B cache-isolation evidence
- [ ] Two visible browser-context screenshots

- [x] New repository and prior-work disclosure
- [x] Taskmaster scope
- [x] Live eligible `gemini-3.7-flash`
- [x] Genuine Google ADK agents
- [x] Official authenticated A2A 1.0 exchange
- [x] Public Cloud Run URL without sign-in
- [x] Firestore and Pub/Sub live workflow
- [x] Three fresh deployed evaluation runs
- [x] Zero evaluated private leakage and unauthorized commitment
- [x] Premium relationship-network UI
- [ ] Human-operated positive commit and network-growth verification

## Repository artifacts

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `SECURITY.md`
- [x] `PRIOR_WORK.md`
- [x] `DEMO_SCRIPT.md`
- [x] `DEVPOST_SUBMISSION.md`
- [x] `SUBMISSION_CHECKLIST.md`
- [x] Mermaid architecture source
- [x] Rendered architecture PNG
- [x] Cloud/model/A2A/authenticity/evaluation/deployment reports
- [x] Video evidence plan

## Final engineering checks

- [x] `make submission-check`
- [x] live A2A integration test
- [x] Cloud deployment verification script
- [x] final container build status
- [x] dependency vulnerability audit
- [x] Python production-image dependency audit
- [x] source and Git-history secret scan
- [x] repository working tree clean after the final evidence commit
- [x] public URL verified after scale-to-zero cold start

## Devpost and media

- [ ] Public repository URL added
- [ ] Devpost description pasted and proofread
- [ ] Architecture PNG uploaded
- [ ] One continuous demo recorded at ≤ 4:00
- [ ] Cloud Run/Logging/Firestore proof visible
- [ ] Video uploaded publicly to YouTube or Vimeo
- [ ] Video verified while signed out
- [ ] Taskmaster selected exactly once
- [ ] Submission URL and video URL recorded here

## Freeze

- [ ] Tag final commit
- [ ] Preserve judging Cloud Run revision and public URL
- [ ] Keep submission artifacts substantively unchanged through judging
- [ ] Scale nonessential resources to zero after recording
