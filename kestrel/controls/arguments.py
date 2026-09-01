"""Check 1 — validate tool arguments.  (Day 1, Block 3)

Every argument the model produces is untrusted input from a hostile caller,
because the caller may have been steered by anything that reached surfaces 1,
2, 4, 6 or 7. Validate against the tool's declared schema, and reject anything
the schema does not describe.

WORKSHOP 1, PHASE B — implement this.
"""

from __future__ import annotations

from typing import Any

from ..boundary import Decision, Session, ToolRequest
from ..tools.registry import ValidationError


def validate_arguments(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Block 3): look up the ToolSpec and validate the arguments against it.
    #
    #   spec = ctx["registry"].get(request.tool)
    #   clean = spec.validate(request.args)
    #   return Decision.allow("schema_ok", args=clean)
    #
    # ...and deny on ValidationError with reason "schema_violation".
    #
    # Then ask the harder question the slide asks: which of Kestrel's tools
    # can express this morning's attack *even with* a valid schema? Those are
    # the ones to narrow, not to guard.
    return Decision.allow("not_implemented")
