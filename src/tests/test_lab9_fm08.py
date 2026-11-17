"""M3 unit tests for ReplyMatchesLedger (FM-08)."""
import pytest

from lab9 import graders
from tests.test_lab9_graders import ctx, trial

pytestmark = pytest.mark.student


def test_reply_matches_ledger_passes_when_amounts_agree():
    t = trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}}])
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is True


def test_reply_matches_ledger_passes_on_denial_without_amount():
    t = trial(refund_vnd=0, refund_count=0, events=[{"kind": "reply", "payload": {"text": "Dạ, đơn O-202 chưa đủ điều kiện hoàn trong 3-5 ngày."}}])
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is True


def test_reply_matches_ledger_catches_misreport():
    t = trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}])
    res = graders.ReplyMatchesLedger().evaluate(ctx(t))
    assert res.value is False
    assert "35000" in (res.reason or "")
    assert "20000" in (res.reason or "")


def test_reply_matches_ledger_catches_paid_claim_when_ledger_zero():
    t = trial(refund_vnd=0, refund_count=0, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35000 VND cho đơn O-909."}}])
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is False


def test_proposal_matches_quote_catches_pre_deduction():
    t = trial(events=[{"kind": "quote", "payload": {"amount_vnd": 35000}}])
    t["result"] = {"proposal_amount": 0}
    assert graders.ProposalMatchesQuote().evaluate(ctx(t)).value is False
    t["result"] = {"proposal_amount": 35000}
    assert graders.ProposalMatchesQuote().evaluate(ctx(t)).value is True
