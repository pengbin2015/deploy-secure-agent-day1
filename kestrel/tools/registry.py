"""The tool registry, and the mechanism that makes mediation provable.

Every tool call runs through ``registry.invoke``. Before invoking, the
ActionBoundary sets a mediation token in a context variable. The registry
records that token alongside the invocation.

    boundary sets token ---> registry.invoke ---> Invocation(token=...)
    anything else calling  -> registry.invoke ---> Invocation(token=None)

Evidence C is then a set comparison: every invocation must carry a token the
boundary issued. An unmediated call is not a code-review opinion, it is a
failing test.
"""

from __future__ import annotations

import contextvars
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

_MEDIATION_TOKEN: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "kestrel_mediation_token", default=None
)


def issue_token() -> str:
    return uuid.uuid4().hex[:12]


class mediating:
    """Context manager the ActionBoundary uses to mark a mediated call."""

    def __init__(self, token: str) -> None:
        self.token = token
        self._reset = None

    def __enter__(self) -> str:
        self._reset = _MEDIATION_TOKEN.set(self.token)
        return self.token

    def __exit__(self, *exc: Any) -> None:
        if self._reset is not None:
            _MEDIATION_TOKEN.reset(self._reset)


class ToolError(Exception):
    """Raised by a tool when its own preconditions fail."""


class ValidationError(Exception):
    """Raised when arguments do not match the tool's declared schema."""


@dataclass
class Param:
    """One declared parameter. The narrower this is, the less an attacker can say."""

    type: type
    required: bool = True
    minimum: int | None = None
    maximum: int | None = None
    max_len: int | None = None
    pattern: str | None = None
    choices: tuple[Any, ...] | None = None

    def check(self, name: str, value: Any) -> Any:
        if self.type is int and isinstance(value, str) and value.strip().isdigit():
            value = int(value)  # models hand back strings; coerce, then check
        if not isinstance(value, self.type):
            raise ValidationError(
                f"{name}: expected {self.type.__name__}, got {type(value).__name__}"
            )
        if self.max_len is not None and len(str(value)) > self.max_len:
            raise ValidationError(f"{name}: longer than {self.max_len} characters")
        if self.minimum is not None and value < self.minimum:
            raise ValidationError(f"{name}: below minimum {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise ValidationError(f"{name}: above maximum {self.maximum}")
        if self.choices is not None and value not in self.choices:
            raise ValidationError(f"{name}: not one of {list(self.choices)}")
        if self.pattern is not None and not re.fullmatch(self.pattern, str(value)):
            raise ValidationError(f"{name}: does not match the required shape")
        return value


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    params: dict[str, Param]
    side_effect: bool = False
    description: str = ""
    #: Wide tools accept free-form strings the caller can shape at will. They
    #: are the Block 3 anti-pattern and are flagged so the console can show it.
    wide: bool = False

    def validate(self, args: dict[str, Any]) -> dict[str, Any]:
        unknown = set(args) - set(self.params)
        if unknown:
            raise ValidationError(f"unexpected arguments: {sorted(unknown)}")
        clean: dict[str, Any] = {}
        for name, spec in self.params.items():
            if name not in args:
                if spec.required:
                    raise ValidationError(f"{name}: missing")
                continue
            clean[name] = spec.check(name, args[name])
        return clean


@dataclass
class Invocation:
    tool: str
    args: dict[str, Any]
    token: str | None
    ts: float = field(default_factory=time.time)

    @property
    def mediated(self) -> bool:
        return self.token is not None


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self.invocations: list[Invocation] = []

    def register(self, spec: ToolSpec) -> ToolSpec:
        self._specs[spec.name] = spec
        return spec

    def replace_all(self, specs: list[ToolSpec]) -> None:
        self._specs = {s.name: s for s in specs}

    def get(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise ToolError(f"no such tool: {name}")
        return self._specs[name]

    def names(self) -> list[str]:
        return sorted(self._specs)

    def specs(self) -> list[ToolSpec]:
        return [self._specs[n] for n in self.names()]

    def invoke(self, name: str, args: dict[str, Any]) -> Any:
        """Run a tool. Records whether the call was mediated."""
        spec = self.get(name)
        self.invocations.append(
            Invocation(tool=name, args=dict(args), token=_MEDIATION_TOKEN.get())
        )
        return spec.fn(**args)

    def reset_invocations(self) -> None:
        self.invocations.clear()


REGISTRY = ToolRegistry()
