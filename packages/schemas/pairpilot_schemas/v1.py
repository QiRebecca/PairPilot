"""Frozen V1 contracts for communities, intent policies, and memory authority."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntentType(StrEnum):
    ROOM_SHARE = "ROOM_SHARE"
    MEAL_COMPANION = "MEAL_COMPANION"
    COFFEE_CHAT = "COFFEE_CHAT"
    EVENT_BUDDY = "EVENT_BUDDY"
    HACKATHON_TEAMMATE = "HACKATHON_TEAMMATE"


class CommunityVisibility(StrEnum):
    PUBLIC = "PUBLIC"
    INVITE_ONLY = "INVITE_ONLY"


class CommunityMembershipRole(StrEnum):
    MEMBER = "MEMBER"
    MODERATOR = "MODERATOR"
    ADMIN = "ADMIN"


class CommunityMembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class MemoryStatus(StrEnum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class Community(BaseModel):
    model_config = ConfigDict(extra="forbid")

    community_id: str = Field(pattern=r"^community_[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=120)
    type: Literal["CONFERENCE_EVENT"] = "CONFERENCE_EVENT"
    location: str = Field(min_length=1, max_length=160)
    start_time: datetime
    end_time: datetime
    visibility: CommunityVisibility = CommunityVisibility.PUBLIC
    membership_policy: Literal["PUBLIC_JOIN", "INVITE_REQUIRED"] = "PUBLIC_JOIN"
    moderator_uids: list[str] = Field(default_factory=list, max_length=50)
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"


class JoinCommunityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite_token: str | None = Field(default=None, min_length=16, max_length=200)


class MemoryActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "CONFIRM",
        "EDIT_AND_CONFIRM",
        "REJECT",
        "ARCHIVE",
        "RESTRICT_SCOPE",
        "TEMPORARILY_DISABLE",
        "ENABLE",
        "STOP_USING",
        "DELETE",
    ]
    content: str | None = Field(default=None, min_length=1, max_length=2_000)
    scope: str | None = Field(default=None, min_length=1, max_length=120)


class NotificationPreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app_enabled: bool = True
    email_enabled: bool = False
    meaningful_events_only: bool = True


class ContactCardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=80)
    telegram: str | None = Field(default=None, max_length=80)
    signal: str | None = Field(default=None, max_length=80)
    wechat: str | None = Field(default=None, max_length=80)
    linkedin: str | None = Field(default=None, max_length=240)
    other_handle: str | None = Field(default=None, max_length=160)


class OutcomeCheckInInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    did_plan_happen: bool
    would_coordinate_again: bool
    agreed_term_inaccurate: bool
    either_person_cancelled: bool = False
    safety_concern: bool = False
    optional_feedback: str | None = Field(default=None, max_length=1_000)
