# PairPilot Final Video Shot List

Target export: 1920×1080 or higher, with the browser content captured at
1440×900 and 100% zoom. Target duration: 3:50. Every timestamp is **planned**
until the exported video is reviewed.

## Shot table

| Shot | Planned time | Screen / route | Required visual proof | Recording note |
| --- | --- | --- | --- | --- |
| 01 | 0:00–0:08 | Landing page | Product name and “agent-operated marketplace” proposition | No browser profile/avatar |
| 02 | 0:08–0:20 | `/app/agent` | One persistent Personal Agent and integrated workspace | Controlled requester only |
| 03 | 0:20–0:38 | `/app/agent` chat | Earlier history plus one live follow-up; composer remains in place | Wait for a real `agent.completed` result |
| 04 | 0:38–0:50 | Inline task card / task context | Card click opens the correct request without losing chat history | Keep old messages visible in the same interface |
| 05 | 0:50–1:03 | Post draft preview | Agent-authored title, description, tags; public/private separation | Ensure no private canary/contact is public |
| 06 | 1:03–1:15 | Publish + Explore detail | Authoritative published status survives refresh; detailed Post opens | Use prepared Post if live mutation is risky |
| 07 | 1:15–1:28 | Candidate ranking | Three candidates with scores/evidence, clear primary/backups | Labels must say simulated/controlled |
| 08 | 1:28–1:42 | Agent Room A, then B | Distinct Agent identities and room transcripts | Show authorship/provenance labels |
| 09 | 1:42–1:50 | Ranking provenance | Rank-change event / updated ordering | Do not imply a static sort is dynamic evidence |
| 10 | 1:50–2:02 | Personal Agent chat | Ask why candidate one ranks first; concise model answer | Use same persistent composer |
| 11 | 2:02–2:15 | Private instruction + public comparison | Private demo canary is absent from Post and A2A room | Avoid displaying the actual sensitive instruction if one exists |
| 12 | 2:15–2:35 | Notification/rank event and Late Candidate detail | Later Post triggered background reevaluation | Prefer persisted before/after event over waiting live |
| 13 | 2:35–2:49 | Requester proposal | Requester approves exact version; state becomes waiting | No match visible yet |
| 14 | 2:49–3:00 | Candidate account | Independent controlled candidate approves same version | Hide login and credentials during account switch |
| 15 | 3:00–3:12 | Requester Match | Exactly one committed Match and unlocked Shared Room | Refresh once to prove persistence |
| 16 | 3:12–3:20 | Shared Room | Simulated participant message and human/Agent authorship | Do not show real contact details |
| 17 | 3:20–3:25 | Network | One relationship with provenance | Focus on relationship created from Match/outcome |
| 18 | 3:25–3:30 | Memory | Confirmed memory and confirmation authority | If showing proposal, make pre-confirmation state explicit |
| 19 | 3:30–3:37 | `/api/health` | `LIVE GEMINI + GOOGLE ADK + A2A`, `gemini-3.7-flash` | Zoom enough for legibility |
| 20 | 3:37–3:44 | Google Cloud Run | Project, production `00042-rob`, Peer `00022-seh`, traffic and healthy state | Crop account identity and billing UI |
| 21 | 3:44–3:49 | Cloud Logging / Firestore | Redacted invocation correlation; authoritative collection type | Never open auth/token/private-data payloads |
| 22 | 3:49–3:55 | `docs/architecture.png` | Conversation → marketplace → A2A → approval → Match flow | End on product name and URL |

## Prepared state

- **Window A:** pre-populated controlled requester on `/app/agent`, with one
  active request, three candidate assessments, at least two Agent Rooms, one
  Match, one relationship and one confirmed Memory.
- **Window B:** controlled candidate account on its current proposal approval
  screen. Keep it outside the capture area until shot 14.
- **Tab C:** requester Explore with the current Post and a Late Candidate result.
- **Tab D:** `/api/health`.
- **Tab E:** production Cloud Run revision `pairpilot-orchestrator-00045-tig`.
- **Tab F:** a pre-filtered, redacted successful Agent invocation log.
- **Tab G:** final architecture PNG.

Exact account credentials live only in the gitignored private judge guide. Do
not copy them into the recording notes, repository or editing project.

## Capture checklist

- [ ] Close notifications, password managers, email and unrelated browser tabs.
- [ ] Disable browser autofill and hide bookmarks/profile chrome if it contains
  personal data.
- [ ] Clear any real contact field from the visible Match/Room cards.
- [ ] Verify every controlled identity is visibly labelled as controlled,
  simulated or demo participant.
- [ ] Confirm the persistent chat has no duplicate optimistic message before
  recording.
- [ ] Confirm inline Task/Post/Room cards navigate with one click.
- [ ] Confirm Explore search/tag filters and detail back-navigation.
- [ ] Confirm Post status and draft survive a hard refresh.
- [ ] Confirm Room, Match, Network and Memory counts match the evidence index.
- [ ] Keep a five-second safety handle before the first line and after the last
  line; trim it from the submitted runtime.

## Post-production verification

1. Watch the exported file once at normal speed with audio.
2. Watch again muted and pause on every account switch, log and Firestore shot
   to check for secrets or private data.
3. Record actual timestamps in `docs/FINAL_EVIDENCE_INDEX.md`; do not estimate.
4. Verify 1080p playback from the public YouTube/Vimeo URL while signed out.
5. Confirm captions spell PairPilot, Google ADK, Vertex AI, Gemini 3.7 Flash,
   Firestore and Pub/Sub correctly.
6. Keep the final duration between 3:40 and 3:55.
