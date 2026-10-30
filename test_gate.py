"""Offline tests for the prerequisite gate. Run: python test_gate.py"""
import json
from support_agent_gated import SupportSession, handle_tool_call


def call(s, name, **kw):
    out, err = handle_tool_call(s, name, kw)
    return json.loads(out), err


def test_blocked_before_verification():
    s = SupportSession()
    r, err = call(s, "process_refund", customer_id="C100", amount=10)
    assert err and r["error"] == "BLOCKED" and s.refunds == []


def test_blocked_for_unverified_customer():
    s = SupportSession()
    call(s, "get_customer", query="bob@example.com")
    r, err = call(s, "process_refund", customer_id="C200", amount=10)
    assert err and r["error"] == "BLOCKED"


def test_allowed_after_verification():
    s = SupportSession()
    call(s, "get_customer", query="alice@example.com")
    r, err = call(s, "process_refund", customer_id="C100", amount=79.99)
    assert not err and r["status"] == "refund_processed"


def test_wrong_customer_id_blocked():
    s = SupportSession()
    call(s, "get_customer", query="alice@example.com")
    r, err = call(s, "process_refund", customer_id="C200", amount=10)
    assert err and "does not match" in r["message"]


def test_failed_lookup_closes_gate():
    s = SupportSession()
    call(s, "get_customer", query="alice@example.com")       # verified
    call(s, "get_customer", query="bob@example.com")         # unverified -> gate closes
    r, err = call(s, "process_refund", customer_id="C100", amount=10)
    assert err and r["error"] == "BLOCKED"


def test_sessions_are_isolated():
    a, b = SupportSession(), SupportSession()
    call(a, "get_customer", query="alice@example.com")
    r, err = call(b, "process_refund", customer_id="C100", amount=10)
    assert err and r["error"] == "BLOCKED"                   # b never verified anyone


def test_invalid_amount():
    s = SupportSession()
    call(s, "get_customer", query="alice@example.com")
    r, err = call(s, "process_refund", customer_id="C100", amount=-5)
    assert err and r["error"] == "invalid_amount"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
