# Positive commit verification

Status: **PENDING REAL HUMAN APPROVAL**.

Automation will not click or call the approval action for the product-evidence
run. When the tagged candidate reaches a current unexpired effect contract, the
operator must click **Approve exact effect** in the visible PairPilot UI.

After that action, record and verify:

- [ ] approval references the displayed proposal version and disclosure hash;
- [ ] one match exists and duplicate approval returns it idempotently;
- [ ] Qi and Maya posts are both `MATCHED`, capacity is consumed, and new
  contacts are closed;
- [ ] other negotiations/holds touching either post are released;
- [ ] Qi–Maya relationship contains match and event provenance;
- [ ] Alice credit increments only if the committed proposal used her
  introduction;
- [ ] scoped editable inferred memory is present and non-authoritative;
- [ ] `match.committed` and two `intent.matched` durable events exist;
- [ ] public refresh preserves the matched result;
- [ ] matched posts no longer appear in the open registry.

Run IDs, proposal/hold IDs, candidate revision, timestamps, and redacted
Firestore/UI evidence will be added immediately after the human action.
