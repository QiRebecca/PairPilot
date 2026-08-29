# Personal Agent OS visual QA

Verified locally against the production build served by FastAPI on 2026-08-29.

| Viewport | Route/state | Result |
|---|---|---|
| 1440 × 900 | `/agent`, empty global conversation | Pass: persistent sidebar, global Qi conversation is the largest surface, contextual decision/work rail is secondary, composer remains fully visible |
| 1440 × 900 | `/explore`, two current seeded posts | Pass: social-style two-column Intent Post feed, owner/agent/authorship/status/provenance visible, no profile or engagement UI |
| 1280 × 800 | routed shell breakpoints | Pass: sidebar and content remain readable without overlap; task/product navigation remains persistent |
| 390 × 844 | `/agent`, empty global conversation | Pass: sidebar collapses to mobile navigation, conversation and composer fit without horizontal overflow, contextual rail follows below |

## Visual hierarchy checks

- Personal Agent conversation is the dominant default surface.
- Technical audit is behind `Developer proof`, not a primary product tab.
- Decision state uses a high-contrast amber treatment; active work uses green;
  draft state uses violet.
- Public, agent-only, and protected draft fields have separate surfaces.
- Room channels use separate tabs and explanatory send controls.
- Synthetic/demo authorship is visible on Explore and shared-room boundaries.

## Interaction checks

- Direct routes load through the FastAPI SPA fallback.
- Browser back/forward state is handled through `popstate`.
- Desktop Explore and mobile Agent screenshots showed no clipping, overlap, or
  illegible contrast.
- Automated React tests cover default Agent home, task-conversation isolation,
  and publish-to-live-run transition.

