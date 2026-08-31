"""Minimum-necessary disclosure guard for all outbound peer messages."""

import re
from dataclasses import dataclass


class DisclosureViolation(ValueError):
    pass


@dataclass(frozen=True)
class MemoryReference:
    memory_id: str
    scope: str
    sensitivity: str
    outbound_disclosure_allowed: bool
    raw_content: str


class OutboundPrivacyGuard:
    """Combine scoped references with deterministic defense-in-depth checks."""

    def validate(
        self, *, natural_language: str, references: list[MemoryReference]
    ) -> str:
        blocked = [
            reference
            for reference in references
            if reference.sensitivity in {"private", "sensitive"}
            or not reference.outbound_disclosure_allowed
        ]
        if blocked:
            raise DisclosureViolation(
                "outbound message references non-disclosable private memory"
            )
        lowered = natural_language.casefold()
        for reference in references:
            if reference.raw_content.casefold() in lowered:
                raise DisclosureViolation("raw memory content must be reformulated")
        prohibited_fragments = (
            "light sleeper",
            "sleep apnea",
            "insomnia",
            "hotel room number",
            "my room number",
            "right now at",
            "currently at",
            "live location",
        )
        if any(fragment in lowered for fragment in prohibited_fragments):
            raise DisclosureViolation("prohibited private phrase detected")
        prohibited_patterns = (
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            r"(?<!\w)\+\d(?:[\s().-]?\d){6,14}(?!\d)",
            (
                r"\b(?:phone|mobile|tel|whatsapp|call|text)\s*[:：]?\s*"
                r"(?:\+?\d[\s().-]?){7,15}(?!\d)"
            ),
            r"(?:电话|手机|微信)\s*[:：]?\s*(?:\+?\d[\s().-]?){7,15}(?!\d)",
            r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
            r"(?<!\d)1[3-9]\d{9}(?!\d)",
            r"\b(?:room|suite)\s*(?:number|no\.?|#)?\s*\d{2,6}\b",
            (
                r"\b\d{1,6}\s+[A-Z0-9 .'-]+\s"
                r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr)\b"
            ),
            r"(?<!\d)-?\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}(?!\d)",
        )
        if any(
            re.search(pattern, natural_language, flags=re.IGNORECASE)
            for pattern in prohibited_patterns
        ):
            raise DisclosureViolation("prohibited identifying detail detected")
        return natural_language
