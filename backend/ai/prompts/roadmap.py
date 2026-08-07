from __future__ import annotations

from typing import Protocol

from ai.client import Prompt


class _HasStrengthsWeaknesses(Protocol):
    strengths: list[str]
    weaknesses: list[str]


_MODULE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "description": {"type": "STRING"},
        "lessons": {"type": "ARRAY", "items": {"type": "STRING"}},
        "exercises": {"type": "ARRAY", "items": {"type": "STRING"}},
        "project": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
            },
            "required": ["title", "description"],
            "nullable": True,
        },
        "estimated_hours": {"type": "INTEGER"},
        "kind": {"type": "STRING", "enum": ["module", "checkpoint", "milestone", "project"]},
    },
    "required": ["title", "description", "lessons", "exercises", "estimated_hours", "kind"],
}

_PHASE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "description": {"type": "STRING"},
        "goal": {"type": "STRING"},
        "estimated_hours": {"type": "INTEGER"},
        "modules": {"type": "ARRAY", "min_items": 2, "max_items": 8, "items": _MODULE_SCHEMA},
    },
    "required": ["title", "goal", "modules"],
}

_ROADMAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "total_weeks": {"type": "INTEGER"},
        "weekly_hours": {"type": "INTEGER"},
        "weekly_goals": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "week": {"type": "INTEGER"},
                    "goal": {"type": "STRING"},
                    "phase_order": {"type": "INTEGER"},
                },
                "required": ["week", "goal", "phase_order"],
            },
        },
        "final_project": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
                "skills_demonstrated": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["title", "description", "skills_demonstrated"],
        },
        # Last on purpose: Gemini reliably follows schema property order, and
        # this lets the SSE parser emit `meta` with complete data before the
        # first phase arrives. Verified against a live streaming call before
        # this schema was written — see this plan's header.
        "phases": {"type": "ARRAY", "min_items": 4, "max_items": 10, "items": _PHASE_SCHEMA},
    },
    "required": [
        "title",
        "summary",
        "total_weeks",
        "weekly_hours",
        "weekly_goals",
        "final_project",
        "phases",
    ],
}

_SYSTEM = (
    "You are a curriculum designer for CareerOS, an AI career mentor. Output "
    "only valid JSON matching the schema. Every phase needs 2-8 modules; every "
    "module needs lessons, exercises, an estimated_hours, and a kind. Include "
    "at least one checkpoint and one milestone somewhere in the roadmap."
)


def build_roadmap_prompt(
    topic: str, level: str, assessment: _HasStrengthsWeaknesses | None = None
) -> Prompt:
    if level == "beginner":
        guidance = (
            "Assume zero prior knowledge. Start from absolute fundamentals and "
            "build up gradually. Include a gentle on-ramp phase before anything else."
        )
    else:
        strengths = ", ".join(assessment.strengths) if assessment and assessment.strengths else "none identified"
        weaknesses = (
            ", ".join(assessment.weaknesses) if assessment and assessment.weaknesses else "none identified"
        )
        if level == "advanced":
            guidance = (
                "This is a revision roadmap — skip fundamentals entirely. The "
                f"learner's assessed strengths are: {strengths}. Their weaknesses "
                f"are: {weaknesses}. Weight phases and modules toward the "
                "weaknesses, include advanced projects, and end with "
                "interview-focused revision for this topic."
            )
        else:
            guidance = (
                "Build the roadmap from the learner's actual assessed level, not "
                f"from scratch. Their strengths are: {strengths} — cover these "
                f"lightly as review. Their weaknesses are: {weaknesses} — give "
                "these real depth and practice."
            )

    user_content = (
        f"Topic: {topic}\n"
        f"Declared/assessed level: {level}\n"
        f"{guidance}\n\n"
        "Design a complete, personalized learning roadmap:\n"
        "- 4-10 learning phases, each with a clear goal and 2-8 modules\n"
        "- weekly_goals spanning total_weeks, each tagged with its phase_order\n"
        "- final_project: one capstone spanning skills from multiple phases, "
        "distinct from any single module's mini project"
    )

    return Prompt(
        system_instruction=_SYSTEM,
        user_content=user_content,
        response_schema=_ROADMAP_SCHEMA,
        temperature=0.7,
        max_output_tokens=8192,
    )
