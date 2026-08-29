# PairPilot Personal Agent OS architecture

## Product decision

PairPilot uses one persistent `qi-agent` principal with two conversation
levels:

- `conversation_global_qi` is the cross-task control surface. Its router sees
  only bounded task summaries.
- every `TaskWorkspace` has a separate `TASK_USER_AGENT` conversation. Task
  messages never enter another task conversation.

This preserves one relationship with the user's Personal Agent without
collapsing unrelated requests into one context window.

## Authoritative product objects

Firestore persists these product projections in addition to the existing
intent, relationship, negotiation, hold, approval, match, and memory records:

| Object | Purpose |
|---|---|
| `task_workspaces` | request identity, lifecycle, task conversation, intent, decisions, proposal, match |
| `conversations` | global and task conversation boundaries |
| `conversation_messages` | user/Qi messages and directive references |
| `decision_inbox` | priority-ordered human decisions |
| `candidate_assessments` | dynamic evidence bands with verified, peer-reported, negotiated, conflict, and uncertainty sections |
| `coordination_rooms` | one task + source intent + target intent + peer-agent room |
| `room_messages` | explicit speaker, authorship, visibility, provenance, and task scope |
| `presentation_directives` | allowlisted UI action plus authoritative entity IDs |

The projection service derives candidate rooms and assessments from actual A2A
messages, beliefs, proposals, approval requests, and matches. It does not invent
candidate facts.

## Routing and presentation authority

The live `gemini-3.7-flash` Personal Agent router returns a validated
`PersonalAgentRoutingResult`: intent classification, an authorized task ID,
user-facing text, and presentation-action types. The server rejects unknown
tasks. Presentation directives reject URLs and allow navigation only for
`OPEN_TASK`, `OPEN_COORDINATION_ROOM`, and `FILTER_EXPLORE`. The frontend uses
directive entity IDs to render records already returned by authoritative APIs.

## Communication boundaries

Coordination Rooms keep three channels structurally separate:

- `PRIVATE_USER_AGENT`: user instructions to Qi;
- `AGENTS_ONLY`: inspectable peer-agent negotiation, with direct human writes
  rejected by schema validation;
- `SHARED_ROOM`: unlocked only after the current demo match, with explicit
  human/agent authorship and a synthetic-participant label.

Agent, Co-pilot, and Human modes control communication workflow only. They do
not grant commitment authority. The existing exact-effect approval and atomic
commit checks remain the only match boundary.

## Internal workers

Dynamic temporary workers are not implemented in this revision. The live
workflow already uses one persistent Qi principal plus task-scoped sessions
with independent Alice, Maya, and Lena Personal Agents. The UI and bootstrap
state report this limitation explicitly; no fixed or fake worker sequence is
shown.

## Routes

`/agent`, `/requests`, `/requests/:taskId`, `/explore`, `/rooms`,
`/rooms/:roomId`, `/matches`, `/network`, `/memory`, and `/audit` are direct-link
safe and support browser back/forward through the History API. `/agent` is the
default logged-in product surface.

