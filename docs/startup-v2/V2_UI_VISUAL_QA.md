# Startup V2 UI refinement and visual QA

Updated: 2026-09-01

Status: `PARTIAL`

This report separates implemented responsive/accessibility behavior from visual
evidence that still requires an authenticated candidate environment. Compilation
and component tests are not treated as visual acceptance.

## Product hierarchy changes

### Request workspace

`/app/requests/:taskId` is now a route-level workspace with the required tabs:

- Conversation (default);
- Overview;
- Post;
- Candidates;
- Agent Rooms;
- Activity;
- Audit.

Conversation reuses the owner's persistent global Personal Agent and supplies the
current `task_id`; opening a Request does not create a disconnected Agent or erase
conversation history. Overview presents the Request, Community, Post,
candidate/contact/negotiation counts, primary/backups, decisions, latest change,
and monitoring state. The remaining tabs expose the authoritative lifecycle
objects without duplicating their state in the frontend.

### Room integration

The `Private with My Agent` channel now embeds the same live, persistent Personal
Agent conversation with the Room's associated Request as active task context.
It no longer behaves as a storage-only message box. Agents-only remains
human-read-only and policy-redacted. Shared Room messages remain explicit
human-authored sends; Agent-drafted shared-message approval is still a remaining
gap.

### Operations

The Admin page was moved from the old dashboard block into a route-level
operations page. It has a dedicated section navigator that collapses to a
horizontal, scrollable control on narrower screens.

## Implemented accessibility behavior

- global visible keyboard focus for buttons and form controls;
- semantic buttons, labels, tables, headings, and navigation landmarks on the
  new Request and Operations pages;
- `aria-current` on active workspace and Admin sections;
- `role="alert"` for new mutation errors and `role="status"` for notices;
- Personal Agent transcript uses an `aria-live` region;
- offline state is announced and does not hide already loaded content;
- `prefers-reduced-motion` disables nonessential animation, smooth scrolling,
  and transitions;
- horizontal navigation remains scrollable rather than squeezed at mobile
  widths.

## Responsive implementation review

| Target | Implemented layout behavior | Visual evidence |
|---|---|---|
| 1440×900 | persistent sidebar, wide content, contextual side panels | Primary authenticated owner journey reviewed live |
| 1280×800 | persistent sidebar, reduced grids | Not captured in a V2 candidate |
| 768×1024 | horizontal App navigation, one-column Room/Admin, three-column Request facts | Not captured in a V2 candidate |
| 390×844 | icon App navigation, single-column cards/forms/facts, horizontal tab scrollers | Not captured in a V2 candidate |

## Surface checklist

| Surface | Route-level implementation | Automated component/build evidence | Authenticated screenshot reviewed |
|---|---|---|---|
| My Agent | yes | yes | desktop |
| Request Overview | yes | yes | desktop |
| Explore | yes | yes | desktop |
| Post Detail | yes | yes | desktop |
| Community | yes | yes | desktop |
| Room | yes | yes | desktop |
| Match | yes | yes | desktop |
| Connections list | yes | yes | desktop |
| Connections graph | yes | build only | no |
| Memory | yes | yes | desktop |
| Decision Inbox | yes | build only | desktop |
| Notifications | yes | yes | desktop |
| Autonomy Center | yes | build only | desktop |
| Admin | yes | build only | no |

## Automated checks

- ESLint: passed.
- TypeScript: passed.
- Frontend component tests: 19 passed, zero failed.
- Production frontend build: passed.
- Request test verifies Conversation is the default and all seven tabs exist.
- Room test verifies Private with My Agent receives the same global conversation
  and the associated Request's task scope.
- Authenticated feature pages are route-split. The main JavaScript chunk is
  approximately 282 kB before gzip; Explore, Rooms, Matches, Connections,
  Memory, Communities, Decisions/Notifications and Admin load on demand.

## Remaining visual acceptance gate

The V2 candidate is deployed at revision `pairpilot-orchestrator-00074-riw`. An
authenticated desktop journey has been reviewed across Agent, Request, Explore,
Post, Community, Room, Match, Connection, Memory and Decision surfaces. The
required four-viewport screenshot matrix is still incomplete, so responsive and
accessibility status remains `PARTIAL`, not `LIVE_VERIFIED`.

Candidate acceptance must capture and inspect every listed surface at all four
target widths, run keyboard-only navigation, verify screen-reader naming and
error announcements, check zoom/reflow, and test slow/offline/reconnect behavior.
