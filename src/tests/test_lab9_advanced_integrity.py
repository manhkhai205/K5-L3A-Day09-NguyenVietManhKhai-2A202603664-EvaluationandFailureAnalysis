"""M7 extra integrity & ratchet tests covering hidden trap patterns."""
import copy

import pytest

from lab9 import gate
from tests.test_lab9_advanced import ROWS, SPEC, _report

pytestmark = pytest.mark.student


def test_advanced_integrity_flags_duplicate_rows_with_same_length():
    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    dup_rows = copy.deepcopy(ROWS[:-1]) + [copy.deepcopy(ROWS[0])]
    dup = _report(dup_rows, {"pass_rate": 1.0})
    assert gate.integrity_check(dup, base, SPEC)


def test_advanced_integrity_flags_evaluator_failures_on_green_run():
    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    broken = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    broken["evaluator_failures"] = ["E-001@11:ApprovalBypass:boom"]
    assert gate.integrity_check(broken, base, SPEC)


def test_advanced_integrity_flags_none_row_and_slice_tampering():
    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    none_row = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    none_row["rows"][0]["pass_rate"] = None
    assert gate.integrity_check(none_row, base, SPEC)

    tampered = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    tampered["rows"][0]["slices"] = []
    assert gate.integrity_check(tampered, base, SPEC)


def test_advanced_integrity_flags_slice_ratchet():
    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    base_spec = {
        **SPEC,
        "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}],
    }
    loose_spec = copy.deepcopy(base_spec)
    loose_spec["slices"][0].pop("no_significant_drop")
    assert gate.integrity_check(base, base, loose_spec, base_spec)
