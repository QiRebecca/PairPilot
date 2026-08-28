"""Idempotent event consumption independent of Pub/Sub redelivery count."""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: str
    idempotency_key: str
    payload: dict[str, object] = field(default_factory=dict)


class IdempotentEventConsumer:
    def __init__(self) -> None:
        self.processed_keys: set[str] = set()

    def consume(
        self, event: DomainEvent, handler: Callable[[DomainEvent], None]
    ) -> bool:
        if event.idempotency_key in self.processed_keys:
            return False
        handler(event)
        self.processed_keys.add(event.idempotency_key)
        return True

