# Real Agent-Driven Multi-User E2E

Date: 2026-08-30 (Asia/Shanghai)

## Result

PASS against the zero-traffic tagged candidate:

`https://real-agent-chat---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`

Final candidate revision: `pairpilot-orchestrator-00024-nef`  
Image digest:
`sha256:135c9fbb0b8305adeebe991c96e4150581a49e4f39889dc7f52379ef161af964`

Production traffic was not changed. It remains 100% on
`pairpilot-orchestrator-00011-xeg`. Revisions `00020-vig`, `00022-dit`,
`00023-xoq`, and the older production revisions remain available for rollback
evidence.

## Controlled users

- User A UID: `TH6daBdwmLQPeHA0noJVGpAnGC53`
- User B UID: `TUQWZjC3yOSxYQHePig3QzF7Mgj1`
- Both accounts were independently Firebase-authenticated and email-verified.
- Agent IDs were distinct.
- Passwords and ID tokens were never printed.

## Final run

User A:

- global conversation:
  `user:TH6daBdwmLQPeHA0noJVGpAnGC53:global`
- task:
  `task_69fbe2b6b6b742b483978f0bf3262b25`
- task conversation:
  `user:TH6daBdwmLQPeHA0noJVGpAnGC53:task:task_69fbe2b6b6b742b483978f0bf3262b25`
- task ADK session: `adk_session_bf6f4c5f61b41a1634f3e22e`
- task invocations:
  `invocation_7a27f03ccc1dbb20345dd56e`,
  `invocation_e5a38c4daadef63ec0625a9b`
- A2A turn: `a2a_turn_c8c66a44ecbb2eec5e868072`
- A2A invocation:
  `a2a_invocation_4b294851d2f34fc193f30070c4c606d4`
- A2A session: `a2a_adk_session_b971020ed95be38b2482c5e4`

User B:

- global conversation:
  `user:TUQWZjC3yOSxYQHePig3QzF7Mgj1:global`
- task:
  `task_6ce1a2c4669e4098810a702f09f268f8`
- task conversation:
  `user:TUQWZjC3yOSxYQHePig3QzF7Mgj1:task:task_6ce1a2c4669e4098810a702f09f268f8`
- task ADK session: `adk_session_cff0f54da519144f32b68658`
- task invocations:
  `invocation_8b38c5eb39b56cf1367b0182`,
  `invocation_dc04246916cfb0bb0e7157f9`
- A2A turn: `a2a_turn_8b3525aa3b6cee72aaf3cee0`
- A2A invocation:
  `a2a_invocation_f20a2e091e56444b894ad6762dac0fba`
- A2A session: `a2a_adk_session_020410cf57ce3f0b0600a1cf`

Both Agents used `gemini-3.7-flash` through Google ADK and ADC.

## Tested sequence

1. Each user sent a free-form global chat message.
2. Each live Agent selected `create_task_workspace` and created a private task.
3. Each user asked a follow-up in the same global ADK session.
4. Each user continued in a separate task-scoped conversation.
5. Each Agent selected `draft_intent_post`.
6. Each user sent the exact publication confirmation.
7. Each Agent selected `publish_intent_post`; no frontend form created the post.
8. Pub/Sub invoked bounded background work with quotas and leases.
9. Both generic user-owned Agents ran live Gemini in distinct persistent A2A
   sessions and produced persisted turns.
10. The platform produced proposal
    `proposal_1c4c8a10249db8501aa467fe`, version 1.
11. User A's approval returned `WAITING_FOR_OTHER_HUMAN`; no match existed yet.
12. User B independently approved the same version; only then did the result
    become `MATCH_COMMITTED` and the shared room unlock.
13. User A attempted to read User B's conversation audit and received HTTP 403.
14. Refresh/bootstrap returned persisted chat history without another model call.

No candidate response, peer reply, or final candidate was manually populated by
the test. The test script supplied only human messages and exact human approval
phrases.

## Pub/Sub candidate isolation

The permanent subscription continues to target the older `multi-user-beta`
tag. To validate a zero-traffic candidate without changing that subscription, a
temporary subscription named `pairpilot-real-agent-chat-e2e` was created with
the candidate URL and the existing OIDC service account. It was deleted
immediately after each run. The permanent subscription, production traffic, and
older revisions were unchanged.

## Security and authority assertions

- different UIDs, Agent IDs, conversations, human-Agent sessions, and A2A
  sessions;
- owner-only conversation and audit access;
- no User A context in User B's Agent;
- public post projections excluded UID, email, private goal, and private budget;
- no fixed peer response fallback;
- publishing required an explicit current human phrase;
- the first human approval could not commit;
- the same proposal version was required from both humans;
- chat history and invocation proof survived refresh;
- the app remained healthy after the match.

## Rollback

The candidate has zero traffic. If traffic is ever promoted and rollback is
needed:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a \
  --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00011-xeg=100
```

The exact reproducible gate is:

```bash
GOOGLE_CLOUD_PROJECT=pairpilot-agentic-ecb84a \
PAIRPILOT_E2E_BASE_URL=https://real-agent-chat---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app \
uv run python scripts/run_real_agent_chat_e2e.py
```
