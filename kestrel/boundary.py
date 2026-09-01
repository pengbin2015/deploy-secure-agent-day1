"""The ActionBoundary: the deterministic chokepoint between the model's
proposal and a real-world effect.

    MODEL  --proposes-->  ACTION BOUNDARY  --permits-->  TOOL executes

Six checks, in this order:

    1. validate tool arguments          Block 3
    2. authorize against session identity   Block 4
    3. scope resources to the caller        Block 4  <- this morning's breach
    4. apply business rules                 Block 4
    5. require approval?                    Day 2, Block 9
    6. apply rate and action limits         Day 2, Block 10

Two guarantees this class exists to provide:

  * every boundary decision emits a SecurityEvent, allow or deny;
  * no tool can execute without a matching SecurityEvent.

The second is the one worth testing. It is the difference between an
architecture you intend and an architecture you have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .config import CONFIG
from .events import ALLOW, DENY, HOLD, LOG, SecurityEvent, new_turn_id
from .surfaces import Surface
from .tools.registry import REGISTRY, ToolError, ToolRegistry, issue_token, mediating


@dataclass
class Session:
    """Who is actually on the other end of the conversation.

    This is established by the surrounding application at authentication time.
    The agent receives an identity; it never establishes one, and it can never
    change one. Nothing the model says may edit these fields.
    """

    session_id: str
    customer_id: int
    roles: tuple[str, ...] = ("customer",)
    channel: str = "web-chat"

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass
class ToolRequest:
    """A proposal. Not yet an action."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    #: Where the instruction that produced this proposal came from. Used for
    #: reporting, never for authorization — provenance informs, identity decides.
    origin_surface: int = int(Surface.USER_MESSAGE)
    scenario_id: str | None = None


@dataclass
class Decision:
    """What one check concluded."""

    decision: str
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, reason: str = "ok", **detail: Any) -> "Decision":
        return cls(ALLOW, reason, detail)

    @classmethod
    def deny(cls, reason: str, **detail: Any) -> "Decision":
        return cls(DENY, reason, detail)

    @classmethod
    def hold(cls, reason: str, **detail: Any) -> "Decision":
        return cls(HOLD, reason, detail)


@dataclass
class BoundaryResult:
    allowed: bool
    result: Any = None
    events: list[SecurityEvent] = field(default_factory=list)
    error: str | None = None

    @property
    def denial(self) -> SecurityEvent | None:
        for e in self.events:
            if e.decision in (DENY, HOLD):
                return e
        return None


CheckFn = Callable[[ToolRequest, Session, dict], Decision]


class ActionBoundary:
    """Every model-driven action crosses this object. No exceptions."""

    #: The order matters and mirrors the teaching order. Resource scoping sits
    #: directly under authorization because they are the two levels that
    #: failed this morning: the caller was authenticated, the resource was not
    #: checked.
    CHECK_ORDER = (
        ("validate_arguments", Surface.TOOL_ARGUMENTS),
        ("authorize_identity", Surface.TOOL_ARGUMENTS),
        ("scope_resources", Surface.TOOL_ARGUMENTS),
        ("business_rules", Surface.TOOL_ARGUMENTS),
        ("require_approval", Surface.TOOL_ARGUMENTS),
        ("apply_limits", Surface.TOOL_ARGUMENTS),
    )

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        controls: Any | None = None,
        log: Any | None = None,
    ) -> None:
        self.registry = registry or REGISTRY
        self.log = log or LOG
        self.controls = controls or load_controls()
        #: Tokens this boundary has issued for permitted calls. Evidence C
        #: compares this against what the registry actually ran.
        self.issued_tokens: set[str] = set()

    # -- the chokepoint ----------------------------------------------------
    def execute(
        self,
        request: ToolRequest,
        session: Session,
        *,
        turn_id: str | None = None,
        ctx: dict[str, Any] | None = None,
    ) -> BoundaryResult:
        turn_id = turn_id or new_turn_id()
        ctx = ctx or {}
        ctx.setdefault("registry", self.registry)
        events: list[SecurityEvent] = []

        for check_name, surface in self.CHECK_ORDER:
            fn: CheckFn = getattr(self.controls, check_name)
            try:
                decision = fn(request, session, ctx)
            except Exception as exc:  # a control that crashes must fail closed
                decision = Decision.deny(
                    "control_error", control=check_name, error=str(exc)
                )
            event = self.log.emit(
                SecurityEvent(
                    surface=int(surface),
                    control=check_name,
                    decision=decision.decision,
                    reason=decision.reason,
                    tool=request.tool,
                    session_id=session.session_id,
                    scenario_id=request.scenario_id,
                    turn_id=turn_id,
                    detail=decision.detail,
                )
            )
            events.append(event)
            if decision.decision in (DENY, HOLD):
                return BoundaryResult(False, None, events, error=decision.reason)
            # A check may rewrite the arguments it validated.
            if "args" in decision.detail:
                request.args = decision.detail["args"]

        # Permitted. Mark the call, run it, and record that it was mediated.
        token = issue_token()
        self.issued_tokens.add(token)
        try:
            with mediating(token):
                result = self.registry.invoke(request.tool, request.args)
        except (ToolError, Exception) as exc:
            events.append(
                self.log.emit(
                    SecurityEvent(
                        surface=int(Surface.TOOL_RESULTS),
                        control="tool_execution",
                        decision=DENY,
                        reason="tool_failed",
                        tool=request.tool,
                        session_id=session.session_id,
                        scenario_id=request.scenario_id,
                        turn_id=turn_id,
                        detail={"error": str(exc)},
                    )
                )
            )
            return BoundaryResult(False, None, events, error=str(exc))

        events.append(
            self.log.emit(
                SecurityEvent(
                    surface=int(Surface.TOOL_ARGUMENTS),
                    control="mediated_execution",
                    decision=ALLOW,
                    reason="permitted_and_executed",
                    tool=request.tool,
                    session_id=session.session_id,
                    scenario_id=request.scenario_id,
                    turn_id=turn_id,
                    detail={"token": token},
                )
            )
        )
        return BoundaryResult(True, result, events)

    # -- Evidence C --------------------------------------------------------
    def mediation_report(self) -> dict[str, Any]:
        """Did anything execute without crossing this boundary?

        This is the architectural invariant, checked against what actually ran
        rather than against what the code appears to do.
        """
        unmediated = [
            i for i in self.registry.invocations
            if i.token is None or i.token not in self.issued_tokens
        ]
        return {
            "total_invocations": len(self.registry.invocations),
            "unmediated": [
                {"tool": i.tool, "args": i.args} for i in unmediated
            ],
            "holds": not unmediated,
        }


def load_controls() -> Any:
    """Import the student controls, or the reference set for facilitator demos.

    Set KESTREL_CONTROLS=reference before the anchor demo to show the same
    attack failing. Teams always work against the student package.
    """
    from .controls import load_boundary_controls

    return load_boundary_controls()
