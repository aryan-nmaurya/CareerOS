from __future__ import annotations

from ai.client import Prompt

_QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "question": {"type": "STRING"},
        "expected_points": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["question", "expected_points"],
}

_SYSTEM = (
    "You are a technical interviewer for CareerOS conducting a mock interview. "
    "Generate interview questions as strict JSON matching the schema. Each "
    "question needs 2-5 expected_points describing what a strong spoken answer "
    "would cover. Questions should be answerable out loud in 1-3 minutes each "
    "— avoid anything requiring a whiteboard or written code."
)


def build_interview_prompt(
    topic: str, level: str, count: int, roadmap_context: list[str] | None = None
) -> Prompt:
    if level == "beginner":
        difficulty = (
            "This is a beginner-level interview — ask foundational questions "
            "about core concepts and terminology, the kind a hiring manager "
            "would use to confirm basic familiarity."
        )
    elif level == "advanced":
        difficulty = (
            "This is an advanced interview — probe deep understanding, "
            "trade-offs, edge cases, and real-world experience a senior "
            "practitioner would have."
        )
    else:
        difficulty = (
            "This is an intermediate interview — practical, hands-on "
            "questions a working professional with some experience should "
            "be able to answer confidently."
        )

    context_line = ""
    if roadmap_context:
        context_line = (
            "\nThe candidate has been studying these topics recently — weight "
            f"some questions toward them: {', '.join(roadmap_context)}."
        )

    user_content = (
        f"Topic: {topic}\n"
        f"Level: {level}\n"
        f"{difficulty}{context_line}\n\n"
        f"Generate exactly {count} questions, each spoken-answer-friendly and "
        "distinct from the others."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
            "type": "ARRAY",
                "items": _QUESTION_SCHEMA,
            },
        },
        "required": ["questions"],
    }

    return Prompt(
        system_instruction=_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.6,
        max_output_tokens=4096,
    )
