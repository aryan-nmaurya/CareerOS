from __future__ import annotations

from ai.client import Prompt

_QUESTION_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING", "enum": ["mcq", "descriptive"]},
        "topic_tag": {"type": "STRING"},
        "question": {"type": "STRING"},
        "options": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "nullable": True,
        },
        "correct_option": {"type": "INTEGER", "nullable": True},
        "expected_points": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "nullable": True,
        },
    },
    "required": ["type", "topic_tag", "question"],
}

_GENERATION_SYSTEM = (
    "You are a technical skill assessor for CareerOS. Generate a skill "
    "assessment as strict JSON matching the provided schema. Mix mcq and "
    "descriptive questions covering distinct subtopics of the given topic. "
    "MCQ questions must have exactly 4 options and a zero-indexed "
    "correct_option, and must NOT include expected_points. Descriptive "
    "questions must have 2-4 expected_points describing what a strong "
    "answer would cover, and must NOT include options or correct_option."
)


def build_generation_prompt(topic: str, level: str) -> Prompt:
    """level is the track's declared experience_level — always
    'intermediate' or 'advanced' here, since beginner tracks never reach
    this function (assessment_service rejects them before calling it)."""
    if level == "advanced":
        difficulty = (
            "This is an advanced revision assessment — skip fundamentals "
            "entirely, probe edge cases, internals, and real-world "
            "tradeoffs a working professional would face."
        )
    else:
        difficulty = (
            "This is a standard intermediate assessment — cover the core "
            "working areas of the topic at a practical, hands-on depth "
            "(for a language: syntax, control flow, functions, data "
            "structures, OOP, error handling, common libraries)."
        )

    user_content = (
        f"Topic: {topic}\n"
        f"Declared experience level: {level}\n"
        f"{difficulty}\n"
        "Generate between 8 and 12 questions total, tagged with concise "
        "lowercase topic_tag values (e.g. 'loops', 'oop', 'file_handling')."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
            "type": "ARRAY",
                "items": _QUESTION_ITEM_SCHEMA,
            },
        },
        "required": ["questions"],
    }

    return Prompt(
        system_instruction=_GENERATION_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.6,
        max_output_tokens=4096,
    )


_GRADING_SYSTEM = (
    "You are grading a technical skill assessment for CareerOS. Score each "
    "descriptive answer from 0 to 10 against its expected points: 10 covers "
    "all points with correct depth, 5 is partially correct or shallow, 0 is "
    "wrong or missing. Give one specific sentence of feedback per answer. "
    "Then write a 2-3 sentence overall summary of the candidate's "
    "demonstrated skill across these answers."
)


def build_grading_prompt(
    topic: str, items: list[tuple[str, list[str], str]]
) -> Prompt:
    """items: (question, expected_points, user_answer) tuples. Gradings in
    the response must come back in this same order — the caller zips them
    back positionally rather than relying on the model echoing an id."""
    blocks = []
    for index, (question, expected_points, answer) in enumerate(items):
        blocks.append(
            f"Question {index + 1}: {question}\n"
            f"Expected points: {', '.join(expected_points)}\n"
            f"Candidate's answer: {answer}"
        )

    user_content = (
        f"Topic: {topic}\n\n"
        + "\n\n".join(blocks)
        + f"\n\nReturn exactly {len(items)} gradings, in the same order as "
        "the questions above."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "gradings": {
            "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "score": {"type": "NUMBER"},
                        "feedback": {"type": "STRING"},
                    },
                    "required": ["score", "feedback"],
                },
            },
            "summary": {"type": "STRING"},
        },
        "required": ["gradings", "summary"],
    }

    return Prompt(
        system_instruction=_GRADING_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.3,
        max_output_tokens=2048,
    )
