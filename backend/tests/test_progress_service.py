from datetime import datetime
from types import SimpleNamespace

import pytest

from services.progress_service import (
    build_progress,
    current_phase_index,
    is_module_complete,
    is_phase_unlocked,
    phase_completion,
    roadmap_completion,
)


def _module(completed: bool):
    return SimpleNamespace(completed_at=datetime(2026, 1, 1) if completed else None)


def _phase(order_index: int, modules: list):
    return SimpleNamespace(order_index=order_index, title=f"Phase {order_index}", modules=modules)


def test_is_module_complete_checks_completed_at():
    assert is_module_complete(_module(True)) is True
    assert is_module_complete(_module(False)) is False


def test_phase_completion_is_the_completed_fraction():
    modules = [_module(True), _module(True), _module(False)]
    assert phase_completion(modules) == pytest.approx(2 / 3)


def test_phase_completion_of_empty_phase_is_zero_not_a_crash():
    assert phase_completion([]) == 0.0


def test_roadmap_completion_spans_all_phases():
    phases = [
        _phase(0, [_module(True), _module(True)]),
        _phase(1, [_module(True), _module(False)]),
    ]
    # 3 of 4 modules complete overall
    assert roadmap_completion(phases) == pytest.approx(3 / 4)


def test_first_phase_is_always_unlocked():
    phases = [_phase(0, [_module(False)])]
    assert is_phase_unlocked(0, phases) is True


def test_phase_unlocked_at_exactly_80_percent_previous_completion():
    # 4 of 5 = exactly 0.8 — the spec's threshold is inclusive
    previous = _phase(0, [_module(True)] * 4 + [_module(False)])
    phases = [previous, _phase(1, [_module(False)])]
    assert is_phase_unlocked(1, phases) is True


def test_phase_locked_just_under_80_percent_previous_completion():
    # 3 of 4 = 0.75 — below the threshold
    previous = _phase(0, [_module(True)] * 3 + [_module(False)])
    phases = [previous, _phase(1, [_module(False)])]
    assert is_phase_unlocked(1, phases) is False


def test_current_phase_is_the_first_incomplete_one():
    phases = [
        _phase(0, [_module(True)]),
        _phase(1, [_module(False)]),
        _phase(2, [_module(False)]),
    ]
    assert current_phase_index(phases) == 1


def test_current_phase_when_everything_is_complete_is_the_last_one():
    phases = [_phase(0, [_module(True)]), _phase(1, [_module(True)])]
    assert current_phase_index(phases) == 1


def test_build_progress_summarizes_everything_in_one_shape():
    phases = [
        _phase(0, [_module(True), _module(True)]),
        _phase(1, [_module(False)]),
    ]

    progress = build_progress(phases)

    assert progress["completed_modules"] == 2
    assert progress["total_modules"] == 3
    assert progress["completion_pct"] == pytest.approx(66.7, abs=0.1)
    assert progress["current_phase_index"] == 1
    assert progress["phases"][0]["unlocked"] is True
    assert progress["phases"][1]["unlocked"] is True  # phase 0 is 100% >= 80%
    assert progress["phases"][1]["completion_pct"] == 0.0
