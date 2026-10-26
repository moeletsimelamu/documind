"""A scripted stand-in for a language model, so no test needs a provider or network access."""

import json
from dataclasses import dataclass, field

from documind.answering.provider import ProviderError


@dataclass
class FakeModel:
    """Returns ``reply`` (a dict is sent as JSON, a string as-is) or raises ``error``."""

    reply: dict[str, object] | str | None = None
    error: ProviderError | None = None
    model: str = "fake-model"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        if isinstance(self.reply, str):
            return self.reply
        return json.dumps(self.reply)
