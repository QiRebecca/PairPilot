"""Minimum-necessary disclosure guard for all outbound peer messages."""

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
        prohibited_fragments = ("light sleeper",)
        if any(fragment in lowered for fragment in prohibited_fragments):
            raise DisclosureViolation("prohibited private phrase detected")
        return natural_language
