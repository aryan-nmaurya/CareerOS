from __future__ import annotations

from typing import Any, Protocol


class _HasCompletedAt(Protocol):
    completed_at: object


class _HasModules(Protocol):
    order_index: int
    title: str
    modules: list[_HasCompletedAt]


def is_module_complete(module: _HasCompletedAt) -> bool:
    return module.completed_at is not None


def phase_completion(modules: list[_HasCompletedAt]) -> float:
    if not modules:
        return 0.0
    completed = sum(1 for m in modules if is_module_complete(m))
    return completed / len(modules)


def roadmap_completion(phases: list[_HasModules]) -> float:
    all_modules = [m for p in phases for m in p.modules]
    if not all_modules:
        return 0.0
    completed = sum(1 for m in all_modules if is_module_complete(m))
    return completed / len(all_modules)


def is_phase_unlocked(phase_index: int, phases: list[_HasModules]) -> bool:
    if phase_index == 0:
        return True
    return phase_completion(phases[phase_index - 1].modules) >= 0.8


def current_phase_index(phases: list[_HasModules]) -> int:
    for i, phase in enumerate(phases):
        if phase_completion(phase.modules) < 1.0:
            return i
    return len(phases) - 1 if phases else 0


def build_progress(phases: list[_HasModules]) -> dict[str, Any]:
    """The full progress summary the roadmap and dashboard endpoints share."""
    total_modules = sum(len(p.modules) for p in phases)
    completed_modules = sum(1 for p in phases for m in p.modules if is_module_complete(m))
    current = current_phase_index(phases)

    return {
        "completion_pct": round(roadmap_completion(phases) * 100, 1),
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "current_phase_index": current,
        "current_phase_title": phases[current].title if phases else None,
        "phases": [
            {
                "order_index": phase.order_index,
                "completion_pct": round(phase_completion(phase.modules) * 100, 1),
                "unlocked": is_phase_unlocked(i, phases),
            }
            for i, phase in enumerate(phases)
        ],
    }
