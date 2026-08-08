from __future__ import annotations

from typing import Iterable

from ai.client import Prompt


_SYSTEM = (
    "You are evaluating a technical mock interview for CareerOS. Return strict JSON "
    "matching the supplied schema. Score each answer's technical knowledge, "
    "communication, and confidence from 0 to 10. Score an empty transcript as 0 "
    "with feedback exactly explaining that it was not answered. Use answer duration "
    "and word count as pacing signals, but do not punish concise, technically strong "
    "answers. Give actionable missing concepts and a better answer for each question."
)


def build_evaluation_prompt(
    topic: str,
    level: str,
    items: Iterable[tuple[str, list[str], str | None, int | None]],
) -> Prompt:
    items = list(items)
    question_blocks: list[str] = []
    for index, (question, expected_points, transcript, duration_s) in enumerate(items, 1):
        answer = transcript or ""
        question_blocks.append(
            f"Question {index}: {question}\n"
            f"Expected points: {', '.join(expected_points)}\n"
            f"Transcript: {answer or '[empty transcript]'}\n"
            f"Answer duration seconds: {duration_s or 0}\n"
            f"Word count: {len(answer.split())}"
        )

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
            "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "technical_score": {"type": "NUMBER"},
                        "communication_score": {"type": "NUMBER"},
                        "confidence_score": {"type": "NUMBER"},
                        "missing_concepts": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "better_answer": {"type": "STRING"},
                        "feedback": {"type": "STRING"},
                    },
                    "required": [
                        "technical_score",
                        "communication_score",
                        "confidence_score",
                        "missing_concepts",
                        "better_answer",
                        "feedback",
                    ],
                },
            },
            "overall_score": {"type": "NUMBER"},
            "technical_score": {"type": "NUMBER"},
            "communication_score": {"type": "NUMBER"},
            "confidence_score": {"type": "NUMBER"},
            "strengths": {"type": "ARRAY", "items": {"type": "STRING"}},
            "weaknesses": {"type": "ARRAY", "items": {"type": "STRING"}},
            "recommendations": {"type": "ARRAY", "items": {"type": "STRING"}},
            "summary": {"type": "STRING"},
        },
        "required": [
            "questions",
            "overall_score",
            "technical_score",
            "communication_score",
            "confidence_score",
            "strengths",
            "weaknesses",
            "recommendations",
            "summary",
        ],
    }

    user_content = (
        f"Topic: {topic}\nLevel: {level}\n"
        f"Evaluate exactly {len(items)} interview answers.\n\n"
        + "\n\n".join(question_blocks)
    )
    return Prompt(
        system_instruction=_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.2,
        max_output_tokens=8192,
    )
