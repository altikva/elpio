# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-05
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the status.

from elpio.status import condition, merge_conditions, now_rfc3339


def test_condition_shape():
    assert condition("Ready", True, reason="Reconciled", message="m") == {
        "type": "Ready",
        "status": "True",
        "reason": "Reconciled",
        "message": "m",
    }
    bad = condition("Ready", False)
    assert bad["status"] == "False" and bad["reason"] == "NotReady"


def test_merge_stamps_a_new_condition():
    out = merge_conditions(None, [condition("Ready", True)], "T0")
    assert out == [
        {"type": "Ready", "status": "True", "reason": "Ready", "message": "", "lastTransitionTime": "T0"}
    ]


def test_merge_preserves_time_when_status_unchanged():
    first = merge_conditions(None, [condition("Ready", True)], "T0")
    second = merge_conditions(first, [condition("Ready", True, message="still up")], "T1")
    assert second[0]["lastTransitionTime"] == "T0"  # unchanged status keeps the original time
    assert second[0]["message"] == "still up"  # but other fields refresh


def test_merge_moves_time_when_status_flips():
    first = merge_conditions(None, [condition("Ready", True)], "T0")
    second = merge_conditions(first, [condition("Ready", False)], "T1")
    assert second[0]["status"] == "False"
    assert second[0]["lastTransitionTime"] == "T1"


def test_merge_keeps_unrelated_conditions():
    base = merge_conditions(None, [condition("Active", True)], "T0")
    out = merge_conditions(base, [condition("Ready", True)], "T1")
    assert {c["type"] for c in out} == {"Active", "Ready"}
    active = next(c for c in out if c["type"] == "Active")
    assert active["lastTransitionTime"] == "T0"  # untouched


def test_now_rfc3339_is_zulu():
    stamp = now_rfc3339()
    assert stamp.endswith("Z") and "T" in stamp and "+" not in stamp
