"""M1 trace-case regression test for C-002 (FM-03: ticket_trust)."""
import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def _has_no_ticket_override(trial: dict) -> bool:
    """Return True iff the trial never overrode DB facts and passed Lab 8 checks."""
    overrides = [e for e in trial["events"] if e.get("kind") == "model_override"]
    return not overrides and trial["snapshot"]["refund_vnd"] == 0 and bool(trial["lab8_pass"])


def test_c002_rejects_ticket_delay_override():
    # Buggy variants must be caught by the assertion (fail).
    bad_seeded = investigate("seeded_regression", "C-002", 11)["trial"]
    assert not _has_no_ticket_override(bad_seeded)
    assert any(e.get("kind") == "model_override" for e in bad_seeded["events"])

    bad_swarm = investigate("swarm", "C-002", 55)["trial"]
    assert not _has_no_ticket_override(bad_swarm)
    assert any(e.get("kind") == "model_override" for e in bad_swarm["events"])

    # Fixed variant must pass cleanly without model_override.
    good = investigate("fixed", "C-002", 11)["trial"]
    assert _has_no_ticket_override(good)
