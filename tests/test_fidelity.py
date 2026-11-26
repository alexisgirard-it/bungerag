from audit_fidelity import verify_fidelity


def test_oriented_formulations_and_long_conversations_preserve_catalog():
    summary = verify_fidelity()
    assert summary["oriented_cases"] >= 8
    assert summary["long_conversations"] >= 2
    assert summary["conversation_turns"] >= 20
