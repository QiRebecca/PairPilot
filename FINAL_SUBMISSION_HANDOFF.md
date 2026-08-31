# PairPilot final submission handoff

This document separates completed repository work from the small set of human
actions that cannot be completed safely by automation. It must not contain
passwords, tokens, private email addresses, or private contact details.

## Submission identity

- Project: **PairPilot — A Marketplace Where Personal Agents Find the Right
  People**
- Track: **Taskmaster**
- Production: <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/>
- Exact live model: `gemini-3.7-flash`
- Deadline: **2026-09-01 09:00 Asia/Tokyo**
- Public submission copy: [DEVPOST_SUBMISSION_FINAL.md](DEVPOST_SUBMISSION_FINAL.md)
- Public judge guide: [docs/JUDGE_TESTING_GUIDE.md](docs/JUDGE_TESTING_GUIDE.md)
- Private local guide: `JUDGE_TESTING_INSTRUCTIONS_PRIVATE.md` (gitignored)

## Repository package prepared

- README describes only the authenticated final V1 and contains every required
  submission section.
- Obsolete README-era prototype claims are indexed as historical context in
  [docs/historical/README_PROTOTYPE_ARCHIVE.md](docs/historical/README_PROTOTYPE_ARCHIVE.md).
- Devpost copy explicitly labels the validation cohort as controlled test
  accounts and avoids claims of organic use, marketplace scale, payment,
  booking, government-ID verification, or autonomous final commitment.
- Judge instructions are split into a public credential-free guide and a
  populated, credential-rotated, gitignored private guide.
- Date-stamped historical reports remain unchanged; current claims point to the
  V1 acceptance report.

## Human owner actions before submission

1. Record final Git SHA, Cloud Run revisions, image digests, worker targets,
   runtime identity and rollback in `SUBMISSION_FREEZE.md` after the last
   production promotion. Replace any provisional revision references in final
   evidence with those frozen values.
2. Commit only reviewed repository files. Create the requested freeze branch
   and annotated tag from a clean commit, push them, then create the separate
   post-hackathon development branch.
3. Verify the repository while signed out. If it remains private, grant access
   to the official Devpost/Google hackathon reviewer accounts named in the
   organizer instructions.
4. Record the four-minute video using controlled accounts. Redact emails,
   passwords, tokens and private user content. Upload it and add the final URL
   and timestamps to Devpost/evidence.
5. Paste the final copy into Devpost, recheck the selected track and links, and
    perform the final submit action before the deadline.

## Freeze rule

After the final tag, make no substantive code, data-model, production behavior,
or documentation-claim changes on the submission branch. Route traffic again
only if the submitted site becomes unavailable; record any emergency rollback
or recovery as an amendment. Future work belongs on
`post-hackathon-development`.

## Evidence wording guardrails

Use “validated using independently authenticated controlled test accounts.”
Do not say or imply:

- organic users or real marketplace scale;
- identity verification beyond control of an email account;
- payment, booking, or safety guarantees;
- a model or Agent can perform final human approval;
- older synthetic or zero-traffic reports tested the final V1.

## Final go / no-go

The submission is **GO** only when all boxes below are true:

- [x] final integrated browser path passed at 1440×900;
- [ ] live Gemini provenance and direct A2A evidence captured;
- [x] two-account approval produced exactly one Match and Shared Room;
- [x] cross-user authorization and private projection checks passed;
- [x] background worker and five-minute reconciliation target the frozen
      production revision;
- [ ] tests, lint, type checking, production build, secret scan and dependency
      audits passed on the freeze commit;
- [x] private judge credentials were rotated, populated locally and tested;
- [ ] final revisions, digests, Git SHA and rollback were recorded;
- [ ] video and public repository links work while signed out;
- [ ] Devpost submission was reviewed and submitted.
