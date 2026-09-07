"""Canonical Startup V2 persistence metadata.

Every durable product entity uses one envelope version even when the payload has
an entity-specific ``version`` field.  Keeping the registry outside the service
modules lets both the Firestore boundary and migrations enforce the same rule.
"""

from __future__ import annotations

V2_SCHEMA_VERSION = 4

V2_ENTITY_COLLECTIONS = (
    "users",
    "personal_agents",
    "communities",
    "community_memberships",
    "task_workspaces",
    "conversations",
    "conversation_messages",
    "intent_posts",
    "intent_private_data",
    "saved_posts",
    "saved_searches",
    "candidate_assessments",
    "candidate_rank_events",
    "coordination_rooms",
    "room_participants",
    "room_messages",
    "proposals",
    "proposal_versions",
    "holds",
    "human_approvals",
    "matches",
    "match_participants",
    "contact_cards",
    "relationships",
    "relationship_events",
    "memories",
    "memory_usage_events",
    "decisions",
    "notifications",
    "notification_settings",
    "user_autonomy_configs",
    "blocks",
    "reports",
    "outcomes",
    "agent_invocations",
    "job_failures",
    "usage_quotas",
    "moderation_actions",
    "operator_job_actions",
    "dead_letter_messages",
    "relationship_usage_events",
    "audit_events",
)

V2_ENTITY_COLLECTION_SET = frozenset(V2_ENTITY_COLLECTIONS)
